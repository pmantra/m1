import dataclasses
import hashlib
import json
import re
import unicodedata

import bs4
import requests
import sqlalchemy
from markdownify import markdownify

from app import create_app
from learn.models.migration import ContentfulMigrationStatus
from learn.utils.migrations import constants
from models import marketing
from utils.log import logger

log = logger(__name__)


def print_article_json() -> None:
    resources = marketing.Resource.query.filter(
        marketing.Resource.contentful_status == ContentfulMigrationStatus.NOT_STARTED,
        marketing.Resource.webflow_url != None,
        marketing.Resource.published_at <= sqlalchemy.func.now(),
        marketing.Resource.content_type.in_(
            [t.name for t in marketing.LibraryContentTypes]
        ),
    )
    log.info("Found resources", count=resources.count())
    resources_html = {}
    for resource in resources:
        res = requests.get(resource.webflow_url)
        if res.ok:
            soup = bs4.BeautifulSoup(res.text)
            if has_video_or_unsupported_embedded_image(soup):
                log.info(
                    "Resource has video or unsupported embedded image; skipping",
                    slug=resource.slug,
                    url=resource.webflow_url,
                )
                continue
            resources_html[str(resource.id)] = get_article_markdown_plus_metadata(
                resource, soup
            )
        else:
            log.error(
                "Received non-2xx/3xx fetching resource; skipping",
                id=resource.id,
                url=resource.webflow_url,
                status_code=res.status_code,
            )
            continue
    log.info("Writing json file")
    print(json.dumps(resources_html, ensure_ascii=False, indent=2))


def get_article_markdown_plus_metadata(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    resource: marketing.Resource, soup: bs4.BeautifulSoup
):
    first_img = soup.img
    if not first_img:
        log.warn(
            "Resource did not contain any images",
            id=resource.id,
            webflow_url=resource.webflow_url,
        )
        # Hero image is a required field, so we can't process whatever this is
        return
    src = first_img.attrs["src"]
    # The first image SHOULD be the header image, since I'm told there are no
    # resources without header images.  Checking for a main-header--img class
    # just in case, but just logging instead of stopping if we don't find it.
    if not has_parent_class(img=first_img, class_name="main-header--img"):
        log.warn(
            "First image did not have parent div class main-header--img; verify",
            id=resource.id,
            webflow_url=resource.webflow_url,
            src=src,
        )
    header_image_asset_id = hashlib.md5(src.encode()).hexdigest()

    # Before modifying the html, get related reads
    related_reads_slugs = get_related_reads_slugs(soup)

    # Collect the html we need
    article_contents_list = []
    # w-container is the class all webflow divs should have
    divs = soup.find_all(class_="w-container")
    # Huge, assumption-making hack because sometimes image-cta divs wrap around
    # w-container divs and I need to preserve the image-cta class to process images
    for i, div in enumerate(divs):
        if has_parent_class(div, class_name="image-cta"):
            divs[i] = divs[i].parent

    # The first div will contain the header image and title,
    # so get the content after those two things
    first_div = divs.pop(0)
    h1_title = first_div.h1
    first_div_content = h1_title.next_sibling
    while first_div_content is not None:
        article_contents_list.append(first_div_content)
        first_div_content = first_div_content.next_sibling

    # Add the rest of the divs, stopping when we hit a div that indicates we're at the end
    # (related reads, provider recs, etc.)
    for div in divs:
        article_element = check_for_and_remove_post_article_content(div)
        if article_element.should_keep:
            article_contents_list.append(article_element.tag)
        if article_element.contains_end:
            break

    html = "".join(
        # This ensures things like curly quotes work instead of showing up
        # as weird characters
        [(obj).encode("latin1").decode("utf8") for obj in article_contents_list]
    )
    # Transform from string back to soup in order to apply html fixes
    # to just the article body
    article_body_soup = bs4.BeautifulSoup(html)
    embedded_entries = {}
    apply_hacky_html_fixes(
        soup=article_body_soup,
        embedded_entries=embedded_entries,
        slug=resource.slug.lower(),
    )
    html = str(article_body_soup)

    return {
        "content_type_id": "article",
        "fields": {
            "title": {"en-US": resource.title},
            "heroImage": {
                "en-US": {
                    "sys": {
                        "type": "Link",
                        "linkType": "Asset",
                        "id": header_image_asset_id,
                    }
                }
            },
            "slug": {"en-US": resource.slug.lower()},
            "medicallyReviewed": {"en-US": True},
            "richText": {"en-US": html_to_markdown(html)},
            # We will take these slugs in the final script and turn them into
            # the actual format Contentful expects
            "relatedReads": {"en-US": related_reads_slugs},
        },
        "embedded_entries": embedded_entries,
    }


def html_to_markdown(html_str: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # .normalize gets rid of \xa0 (non-breaking space in Latin-1) and possibly
    # other stuff
    # \u200d (zero-width joiner) is unnecessary
    normalized_html = unicodedata.normalize("NFKD", html_str).replace("\u200d", "")
    # The default heading style is "UNDERLINED" which we don't want
    md = markdownify(normalized_html, heading_style="ATX")
    return apply_hacky_markdown_fixes(md)


def apply_hacky_markdown_fixes(md: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Some weird webflow notation shows up, e.g.
    # {| type: message | label: Book Practitioner | btnclass: btn btn-tertiary |}
    # This replaces this whole string with just the label (here, Book Practitioner)
    md = re.sub(r"\{\|.+label: (.+)\|.+\|\}", r"\1", md)
    # If bold text is followed directly by a non-whitespace character (\S) add a
    # space after it to try and get it formatted correctly and not just be asterisks
    md = re.sub(r"\*\*(\S[^\*]+)\*\*(\S+)", r"**\1** \2", md)
    # Four asterisks in a row means we have two bold things in a row,
    # which can just be combined
    return md.replace("****", "")


def has_video_or_unsupported_embedded_image(soup: bs4.BeautifulSoup):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    imgs = soup.find_all("img")
    for img in imgs:
        # I don't know why these invisible images are here but get rid of them
        if "placeholder.svg" in img.attrs.get("src"):
            img.extract()
            continue
        # This is the only way I can think to do this--remove a specific inline
        # clipboard image in two articles
        if (
            "_g1__xlgwTinfP2HTx9XFcFu72-JgV1rgjIvS8CSLVBBVKFTV-mP_udJYJ6jiRIWwxHTUz5An2YEFJowxz2O71IFbOw0rLQ9cstfMwe-v-ygdc2cGsJiO4HWeIGPChCu-_iPRGxMx226fsg1ViIr_VUoVPeerwQfMJkcexsT0A4uyvSt9HPfTrmoA4EGr.png"
            in img.attrs.get("src")
        ):
            log.warn("Removing clipboard image", src=img.attrs.get("src"))
            img.extract()
            continue
        # There is one article with an image in an accordion, just remove the image
        if has_parent_class(img=img, class_name="accordion-answer"):
            img.extract()
            log.warn("Removing image from accordion", src=img.attrs.get("src"))
            continue
        if (
            not has_parent_class(img=img, class_name="main-header--img")
            and not img_is_after_article_body(img)
            and "accordion-arrow" not in img.attrs.get("class", [])
            and not has_parent_class(img=img, class_name="checklist-container")
            and not has_parent_class(img=img, class_name="image-cta")
            and not has_figure_parent(img)
            and not has_checklist_parent_class(img)
        ):
            return True
    if soup.video:
        return True


def has_parent_class(img: bs4.element.Tag, class_name: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for parent in img.parents:
        if parent.name == "div":
            classes = parent.attrs.get("class", [])
            if class_name in classes:
                return True


def img_is_after_article_body(img: bs4.element.Tag):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for parent in img.parents:
        if parent.name == "div":
            if div_is_after_article_body(parent):
                return True


def has_figure_parent(img: bs4.element.Tag):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for parent in img.parents:
        if parent.name == "figure":
            return True


def has_checklist_parent_class(img: bs4.element.Tag):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for parent in img.parents:
        if parent.name == "div":
            classes = parent.attrs.get("class", [])
            if "checklist-container" in classes:
                return True


def div_is_after_article_body(div: bs4.element.Tag):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    classes = div.attrs.get("class", [])
    # These are all classes of divs that only appear after the article body
    # e.g. related reads, "book with these providers," etc.
    if (
        "single-provider-section" in classes
        or "provider-badge" in classes
        or "related-articles" in classes
        or "related-header" in classes
        or "related-item" in classes
        or "explore-library-link" in classes
        or "providers" in classes
        or "single-provider-hdr" in classes
        or "provider-badge--container" in classes
        or "provider-image" in classes
        or "talk-to-provider" in classes
        or "talk-to-provider-block" in classes
    ):
        return True


def get_related_reads_slugs(soup: bs4.BeautifulSoup):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    header = soup.find(class_="related-header")
    if header:
        related_item_links = header.find_all_next(class_="related-item")
        return [a.attrs["href"].split("/")[-1].strip() for a in related_item_links]


def apply_hacky_html_fixes(soup: bs4.BeautifulSoup, embedded_entries: dict, slug: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Some webflow articles go straight from h1 to h4 or even h5
    # This fixes those erroneous headers while leaving legit h4s/h5s alone
    fix_header_sizes(soup)
    take_line_breaks_out_of_bold_and_italics(soup)
    escape_list_item_line_breaks_and_remove_from_end(soup)
    replace_accordions(soup=soup, embedded_entries=embedded_entries, slug=slug)
    replace_checklists(soup=soup, embedded_entries=embedded_entries, slug=slug)
    replace_embedded_images(soup=soup, embedded_entries=embedded_entries)


def fix_header_sizes(soup: bs4.BeautifulSoup):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    largest_body_header = soup.h2 or soup.h3 or soup.h4 or soup.h5
    if largest_body_header:
        # The 2 in "h2" or whatever
        largest_body_header_size = int(largest_body_header.name[1])
        if largest_body_header_size > 2:
            log.debug(f"Headers go from h1 to h{largest_body_header_size}")
            # Figure out how much larger you need to make the existing headers
            # This will not fix articles whose headers jump from e.g. h2 to h4,
            # but this is not a situation we know exists in our articles
            header_transformation_size = largest_body_header_size - 2
            current_tag_size = largest_body_header_size
            while current_tag_size < 6:
                for header in soup.find_all(f"h{current_tag_size}"):
                    log.debug(f"Fixing header: {header}")
                    header.name = f"h{current_tag_size - header_transformation_size}"
                current_tag_size += 1


def escape_list_item_line_breaks_and_remove_from_end(soup: bs4.BeautifulSoup):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Markdown doesn't handle line breaks within list items well, so we're
    # going to change them to a magic string and change them back in the end
    # Also if a line break is at the end of the list item, it's probably
    # unnecessary and shouldn't get rendered anyway?  Let's remove it
    list_items = soup.find_all("li")
    for li in list_items:
        for index, item in enumerate(li.contents):
            if isinstance(item, bs4.element.Tag) and item.name == "br":
                if index == (len(li.contents) - 1):
                    item.extract()
                else:
                    item.replace_with(constants.LINE_BREAK_REPLACEMENT_STRING)
            # I don't know if \ns occur in the article body in the wild, but
            # just in case, replace those with the magic string also
            elif isinstance(item, str) and "\n" in item:
                li.contents[index] = item.replace(
                    "\n", constants.LINE_BREAK_REPLACEMENT_STRING
                )


def take_line_breaks_out_of_bold_and_italics(soup: bs4.BeautifulSoup):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # For some reason, when there is a line break that starts or ends a bold
    # or italics tag, it can disappear.  This takes those line breaks out of
    # the tag because it's not like you need a bolded line break anyway...
    emphasis_tags = soup.find_all(["strong", "em", "b", "i"])
    # There may be overlap with these tags, but hopefully too rare to matter
    for tag in emphasis_tags:
        # Removes all line breaks from the beginning of the tag
        while len(tag.contents) > 0 and (
            (
                isinstance(tag.contents[0], bs4.element.Tag)
                and tag.contents[0].name == "br"
            )
            # Also removes space in case there's a tag with just a space in it...
            or tag.contents[0] == " "
        ):
            whitespace = tag.contents[0].extract()
            tag.insert_before(whitespace)
        # Removes all line breaks from the end of the tag
        while len(tag.contents) > 0 and (
            (
                isinstance(tag.contents[-1], bs4.element.Tag)
                and tag.contents[-1].name == "br"
            )
            # Also removes space in case there's a tag with just a space in it...
            or tag.contents[-1] == " "
        ):
            whitespace = tag.contents[-1].extract()
            tag.insert_after(whitespace)


def replace_accordions(soup: bs4.BeautifulSoup, embedded_entries: dict, slug: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    accordions = []
    # There is no reliable class for an accordion container div, and worse, the
    # div may contain a header that needs to be extracted before turning it all
    # into an accordion entry
    accordion_children = soup.find_all(class_="accordion-item")
    seen = set()
    # Using a set to ensure uniqueness, but storing in a list to preserve order
    accordion_tags = [
        child.parent
        for child in accordion_children
        if not (child.parent in seen or seen.add(child.parent))  # type: ignore[func-returns-value] # "add" of "set" does not return a value (it only ever returns None)
    ]
    for i, accordion in enumerate(accordion_tags):
        # Remove all the arrow images that are in accordions
        for img in accordion.find_all("img"):
            img.extract()
        # There may be a header that's inside the accordion parent div meant as
        # a header for the accordion, but accordions don't have header fields,
        # so take it out
        first_child = accordion.contents and accordion.contents[0]
        if first_child.name in ["h2", "h3", "h4", "h5"]:
            accordion_header = accordion.contents[0].extract()
            accordion.insert_before(accordion_header)

        accordion_id = hashlib.md5(accordion.get_text().encode()).hexdigest()
        suffix = f"-{i + 1}" if len(accordion_tags) > 1 else ""
        accordion_dict = {
            "name": f"{slug}{suffix}",
            "id": accordion_id,
            "items": [],
            "heading_level": None,
        }

        item_tags = accordion.find_all(class_="accordion-item")
        for item_tag in item_tags:
            # Please say accordion items don't have headers in them
            headers = item_tag.find_all(["h2", "h3", "h4", "h5"])
            if not accordion_dict["heading_level"]:
                accordion_dict["heading_level"] = headers[0].name
            item_body = item_tag.find(class_="accordion-answer")
            # Can we assume that whatever is in the item that isn't the body
            # is the header?
            accordion_dict["items"].append(  # type: ignore[union-attr] # Item "Sequence[str]" of "Optional[Sequence[str]]" has no attribute "append" #type: ignore[union-attr] # Item "None" of "Optional[Sequence[str]]" has no attribute "append"
                {
                    "header": item_body.previous_sibling.text,
                    "rich_text": html_to_markdown(str(item_body)),
                }
            )
        # Replace the accordion in the html with a string to be swapped out for
        # the embedded entry at the very end
        # Making it an h1 so it'll end up as its own rich text node, which can
        # be replaced without modifying what comes before and after it
        fake_h1 = soup.new_tag("h1")
        fake_h1.string = constants.ACCORDION_REPLACEMENT_STRING
        accordion.replace_with(fake_h1)
        # Order is going to matter here
        accordions.append(accordion_dict)
    embedded_entries["accordions"] = accordions


def replace_checklists(soup: bs4.BeautifulSoup, embedded_entries: dict, slug: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    checklists = soup.find_all(class_="checklist-container")
    callouts = []
    for i, checklist in enumerate(checklists):
        # Remove all the checkmark images that are in checklists
        for img in checklist.find_all("img"):
            img.extract()
        # There could be multiple checklist-lists 😭
        list_item_divs = [
            div.extract() for div in checklist.find_all(class_="checklist-list")
        ]
        callout_str = str(checklist)
        for list_item_div in list_item_divs:
            # Replace any headers in the body with bold text
            body_headers = list_item_div.find_all(["h2", "h3", "h4", "h5"])
            for header in body_headers:
                # ...But avoid double-bolding
                if (
                    header.contents
                    and isinstance(header.contents[0], bs4.element.Tag)
                    and header.contents[0].name == "strong"
                ):
                    header.name = "p"
                else:
                    header.name = "strong"
                header.insert_after(soup.new_tag("br"))
                header.insert_after(soup.new_tag("br"))
            callout_str += str(list_item_div)

        suffix = f"-{i + 1}" if len(checklists) > 1 else ""
        callouts.append(
            {"name": f"{slug}{suffix}", "body": html_to_markdown(callout_str)}
        )
        # Replace the checklist in the html with a string to be swapped out for
        # the embedded entry at the very end
        # Making it an h1 so it'll end up as its own rich text node, which can
        # be replaced without modifying what comes before and after it
        fake_h1 = soup.new_tag("h1")
        fake_h1.string = constants.CALLOUT_REPLACEMENT_STRING
        checklist.replace_with(fake_h1)
    embedded_entries["callouts"] = callouts


def replace_embedded_images(soup: bs4.BeautifulSoup, embedded_entries: dict):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Images should have already been all uploaded in previous script
    image_cta_divs = soup.find_all(class_="image-cta")
    embedded_images = []

    # I'm counting on there only being one type of image in one article--
    # image-ctas or figures, not both 😓 but will check obv
    for div in image_cta_divs:
        # If it has an image-cta--img class inside, use that to try and avoid
        # misclassifying non-caption text as captions :(
        if div.find(class_="image-cta--img"):
            div = div.find(class_="image-cta--img")
        # Possible if the image was extracted in has_video_or_unsupported_embedded_image
        if not div.img:
            continue
        src = div.img.attrs["src"]
        asset_id = hashlib.md5(src.encode()).hexdigest()
        div.img.extract()

        caption = None
        # Assume any other text in the div is a caption
        if div.text:
            caption_html = "".join(str(content) for content in div.contents)
            caption = html_to_markdown(caption_html)
        embedded_images.append({"asset_id": asset_id, "caption": caption})

        fake_h1 = soup.new_tag("h1")
        # Different magic strings for embedded image entries and embedded assets
        if caption:
            fake_h1.string = constants.IMG_W_CAPTION_REPLACEMENT_STRING
        else:
            fake_h1.string = constants.IMG_REPLACEMENT_STRING
        div.replace_with(fake_h1)

    figures = soup.find_all("figure")
    for figure in figures:
        src = figure.img.attrs["src"]
        asset_id = hashlib.md5(src.encode()).hexdigest()
        figure.img.extract()

        # Assume the caption is in a figcaption tag
        caption = figure.figcaption and html_to_markdown(str(figure.figcaption))
        embedded_images.append({"asset_id": asset_id, "caption": caption})

        fake_h1 = soup.new_tag("h1")
        if caption:
            fake_h1.string = constants.IMG_W_CAPTION_REPLACEMENT_STRING
        else:
            fake_h1.string = constants.IMG_REPLACEMENT_STRING
        figure.replace_with(fake_h1)

    embedded_entries["embedded_images"] = embedded_images


@dataclasses.dataclass
class ArticleContentElement:
    tag: bs4.element.Tag
    contains_end: bool
    should_keep: bool


def check_for_and_remove_post_article_content(
    tag: bs4.element.Tag,
) -> ArticleContentElement:
    elem = ArticleContentElement(tag=tag, contains_end=False, should_keep=True)
    # If tag is a div, check if it's article-ending
    # If it is, we return and indicate we've reached the end and shouldn't keep this div
    if elem.tag.name == "div":
        if div_is_after_article_body(elem.tag):
            elem.contains_end = True
            elem.should_keep = False
            return elem
    # Whether or not tag is a div, check its children for article-ending divs
    if elem.tag.contents:
        for i, child in enumerate(elem.tag.contents):
            # "Contents" could also be just a string (e.g. the contents of a p tag)
            # which shouldn't be treated as a child
            if isinstance(child, bs4.element.Tag):
                child_elem = check_for_and_remove_post_article_content(child)
                if child_elem.contains_end:
                    if child_elem.should_keep:
                        # Keep contents up to the index of the object that contains the end
                        # (Slicing excludes the end)
                        elem.tag.contents = elem.tag.contents[0 : (i + 1)]
                    else:
                        # Keep contents up to the index before the object we shouldn't keep
                        # (If i is 0, this results in an empty array)
                        elem.tag.contents = elem.tag.contents[0:i]
                    elem.contains_end = True
                    # Stop iterating since we've found the end of the article
                    break
    return elem


if __name__ == "__main__":
    with create_app().app_context():
        print_article_json()

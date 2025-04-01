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
from learn.utils.migrations import constants, create_article_json
from models import marketing
from utils.log import logger

log = logger(__name__)


def print_admin_article_json() -> None:
    content_types = [t.name for t in marketing.LibraryContentTypes]
    # This is no longer a supported content type but some admin articles exist
    # with it and need to be migrated...apparently
    content_types.append("curriculum_step")
    resources = marketing.Resource.query.filter(
        marketing.Resource.contentful_status == ContentfulMigrationStatus.NOT_STARTED,
        marketing.Resource.resource_type == marketing.ResourceTypes.ENTERPRISE,
        marketing.Resource.webflow_url == None,
        marketing.Resource.published_at <= sqlalchemy.func.now(),
        marketing.Resource.content_type.in_(content_types),
    )
    resources_html = {}
    missing_hero_imgs = []
    for resource in resources:
        soup = bs4.BeautifulSoup(resource.body)
        if has_nested_bullets(soup):
            log.warn("Resource has nested bullets; skipping")
            continue
        resources_html[str(resource.id)] = get_admin_article_markdown_plus_metadata(
            resource=resource, soup=soup, missing_imgs=missing_hero_imgs
        )
    # Just for the benefit of the content team to replace these images later
    print(missing_hero_imgs)

    print(json.dumps(resources_html, ensure_ascii=False, indent=2))


def has_nested_bullets(soup: bs4.BeautifulSoup):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # This is mostly so I can avoid migrating one resource that I hate
    lists = soup.find_all(["ul", "ol"])
    for list_tag in lists:
        if list_tag.ul or list_tag.ol:
            return True


def get_admin_article_markdown_plus_metadata(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    resource: marketing.Resource, soup: bs4.BeautifulSoup, missing_imgs: list
):
    slug = resource.slug.lower()
    # Assume the first image is the header. On QA1 I couldn't find any articles
    # for which that wasn't the case.
    header_img = soup.img
    hero_img_or_none = None
    if header_img:
        header_img.extract()
        src = header_img.attrs["src"]
        # See if we need to replace with the placeholder
        res = None
        try:
            res = requests.get(src)
        except Exception:
            pass
        if res and res.ok:
            header_image_asset_id = hashlib.md5(src.encode()).hexdigest()
        else:
            missing_imgs.append(slug)
            # Sorry.  This is the placeholder asset id in all environments 😐
            header_image_asset_id = "be3456dd7bce035dbd113f8265d521a9"
    else:
        missing_imgs.append(slug)
        header_image_asset_id = "be3456dd7bce035dbd113f8265d521a9"
    hero_img_or_none = {
        "en-US": {
            "sys": {
                "type": "Link",
                "linkType": "Asset",
                "id": header_image_asset_id,
            }
        }
    }

    embedded_entries = {"embedded_images": [], "callouts": [], "accordions": []}
    related_reads_slugs = extract_related_reads_and_get_slugs(soup)
    apply_hacky_admin_html_fixes(
        soup=soup,
        embedded_entries=embedded_entries,
        slug=slug,
    )
    html = str(soup)
    md = html_to_markdown(html)
    md = apply_hacky_admin_markdown_fixes(
        md=md,
        embedded_entries=embedded_entries,
        slug=slug,
    )

    return {
        "content_type_id": "article",
        "fields": {
            "title": {"en-US": resource.title},
            "heroImage": hero_img_or_none,
            "slug": {"en-US": slug},
            "medicallyReviewed": {"en-US": False},
            "richText": {"en-US": md},
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
    # Underscores are used in admin articles for emphasis instead of double asterisks
    # However single asterisks are used because admin articles hate me personally
    # Hopefully legit single asterisks are at the end of lines and won't affect
    # text they shouldn't affect
    md = markdownify(
        normalized_html,
        heading_style="ATX",
        escape_underscores=False,
        escape_asterisks=False,
    )
    return md


def apply_hacky_admin_html_fixes(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    soup: bs4.BeautifulSoup, embedded_entries: dict, slug: str
):
    remove_post_article_content(soup)
    replace_headers_in_lists_with_bold(soup)
    create_article_json.fix_header_sizes(soup)
    replace_checklists(soup=soup, embedded_entries=embedded_entries, slug=slug)
    create_article_json.escape_list_item_line_breaks_and_remove_from_end(soup)
    replace_embedded_images(soup=soup, embedded_entries=embedded_entries)


def extract_related_reads_and_get_slugs(soup: bs4.BeautifulSoup):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    slugs = []
    elem_containing_rr_header = soup.find(string=re.compile("Related reads"))
    if elem_containing_rr_header:
        to_extract = []
        for sib in elem_containing_rr_header.next_siblings:
            if sib.name == "a":
                # There was a ref!!!!!!!!!!!
                href = sib.attrs.get("href") or sib.attrs.get("ref")
                # There was an EMPTY A TAG
                if not href:
                    continue
                slugs.append(href.split("/")[-1].strip())
                to_extract.append(sib)
            # We've reached something that's not a related read link
            # Let's break in case this is that resource that had sources after related reads
            elif not re.fullmatch(r"\s+", sib.text):
                break
        for a in to_extract:
            a.extract()
        # Risky but the element ought to be a navigable string...if not we'll deal
        new_text = re.sub("#+ ?Related reads", "", elem_containing_rr_header.text)
        new_navigable_string = soup.new_string(new_text)
        elem_containing_rr_header.replace_with(new_navigable_string)
    return slugs


def apply_hacky_admin_markdown_fixes(md: str, embedded_entries: dict, slug: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    note_numbered_lists(md, slug)
    md = fix_markdown_headers(md)
    md = replace_quotes_with_callouts(
        md=md, embedded_entries=embedded_entries, slug=slug
    )
    md = replace_curly_brace_links_with_normal_ones(md)
    return md


def remove_post_article_content(soup: bs4.BeautifulSoup):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for p in soup.find_all("p"):
        if "Read more like this" in p.text:
            p.extract()
    # hrs sometimes appear post-article and we don't support them in general
    for hr in soup.find_all("hr"):
        hr.extract()
    # The divs at the end that have an image and button saying "talk to a
    # provider", "message a CA" etc.
    for div in soup.find_all("div"):
        if "bumpers" in div.attrs.get("class", []):
            div.extract()


def replace_embedded_images(soup: bs4.BeautifulSoup, embedded_entries: dict):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for img in soup.find_all("img"):
        src = img.attrs["src"]
        asset_id = hashlib.md5(src.encode()).hexdigest()
        embedded_entries["embedded_images"].append(
            {"asset_id": asset_id, "caption": None}
        )

        fake_h1 = soup.new_tag("h1")
        fake_h1.string = constants.IMG_REPLACEMENT_STRING
        img.replace_with(fake_h1)


def replace_checklists(soup: bs4.BeautifulSoup, embedded_entries: dict, slug: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    checklists = soup.find_all(class_="checklist")
    for i, checklist in enumerate(checklists):
        # There may be a span which serves as a tiny title, which callouts don't support
        checklist.span.extract()
        headers = checklist.find_all(["h2", "h3", "h4", "h5"])
        # Replace any headers in the body with bold text
        for header in headers:
            header.name = "strong"
            # Yes we're creating these just to turn them into magic strings later
            header.insert_after(soup.new_tag("br"))
            header.insert_after(soup.new_tag("br"))
        suffix = f"-{i + 1}" if len(checklists) > 1 else ""
        embedded_entries["callouts"].append(
            {"name": f"{slug}{suffix}", "body": html_to_markdown(str(checklist))}
        )
        # Replace the checklist in the html with a string to be swapped out for
        # the embedded entry at the very end
        # Making it an h1 so it'll end up as its own rich text node, which can
        # be replaced without modifying what comes before and after it
        fake_h1 = soup.new_tag("h1")
        fake_h1.string = constants.CALLOUT_REPLACEMENT_STRING
        checklist.replace_with(fake_h1)


def replace_headers_in_lists_with_bold(soup: bs4.BeautifulSoup):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    lists = soup.find_all(["ul", "ol"])
    for list_tag in lists:
        headers = list_tag.find_all(["h2", "h3", "h4", "h5"])
        for header in headers:
            header.name = "strong"
            # Yes we're creating these just to turn them into magic strings later
            header.insert_after(soup.new_tag("br"))
            header.insert_after(soup.new_tag("br"))


def note_numbered_lists(md: str, slug: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # There are some markdown-style numbered lists in the html, i.e. 1. 2. 3.
    # If there are any line breaks in there, it messes up the numbering and
    # turns it into 1. 1. 1.  Just print them so we can check
    if re.search(r"(^\d+\. )", md, flags=re.MULTILINE):
        print(f"Numbered list in resource {slug}")


def replace_curly_brace_links_with_normal_ones(md: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Some weird notation shows up, e.g.
    # {| type: message | label: Book Practitioner | url: google.com |}
    # This replaces this whole string with a markdown link where the text is the
    # label and the url is the uh url, e.g. [Book Practitioner](google.com)
    md = re.sub(r"\{\|.+label: (.+?) ?\| url: ?([^\|]+)\|?(.+?)?\}", r"[\1](\2)", md)
    # If there are any inline ones of these (i.e. there's non-whitespace
    # characters after it) without urls, replace them with just the label
    matches = re.findall(r"(\{\|.+label: (.+?) ?\|.+?\|\}).+\S+", md)
    for match_tuple in matches:
        md = re.sub(re.escape(match_tuple[0]), match_tuple[1], md)
    # If they're not inline and don't have a url, remove them
    return re.sub(r"\{\|((?!url:).)*\}", "", md)


def fix_markdown_headers(md: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # This isn't going to catch one article I found with headers in BULLET POINTS
    # but it was just one anyway
    # Matches # chars at the start of a line if followed by a non-# char and looks
    # for the shortest one--aka the largest header
    # (Ignores if it's just one # because that could be a fake callout/image h1)
    if re.search(r"^(##+)[^#]", md, flags=re.MULTILINE):
        # If there are no # sequences, then just cut off the while
        while (
            min(re.findall(r"^(##+)[^#]", md, flags=re.MULTILINE), default="##") != "##"
        ):
            # Uses lookahead so the char after # doesn't get matched (and replaced)
            # Replaces #### strings with themselves but one char shorter until the
            # largest header is ## (h2)
            md = re.sub(
                "^(##+)(?=[^#])", lambda m: f"{m[0][0:-1]}", md, flags=re.MULTILINE
            )
    # Add a space after the hashes because why not; most are missing that I've seen
    md = re.sub("^(##+)(?=[^#])", lambda m: f"{m[0]} ", md, flags=re.MULTILINE)
    return md


def replace_quotes_with_callouts(md: str, embedded_entries: dict, slug: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # findall here returns a list of tuples.  Item 1 in the tuple is the string
    # matching the first capturing group (includes the > ) and item 2 in the
    # tuple is the string matching the second capturing group (does not include >)
    quote_matches = re.findall(r"\n(> ?(.+))\n", md)
    for i, match_tuple in enumerate(quote_matches):
        md = re.sub(
            re.escape(match_tuple[0]), f"# {constants.CALLOUT_REPLACEMENT_STRING}", md
        )
        suffix = f"-{i}" if len(quote_matches) > 1 else ""
        embedded_entries["callouts"].append(
            {"name": f"{slug}{suffix}", "body": html_to_markdown(match_tuple[1])}
        )
    return md


if __name__ == "__main__":
    with create_app().app_context():
        print_admin_article_json()

from io import BytesIO, StringIO
from urllib.request import urlopen

import lxml.html
from misaka import HtmlRenderer, Markdown
from werkzeug.datastructures import FileStorage

from models.images import upload_and_save_image
from models.marketing import Resource
from storage.connection import db

rndr = HtmlRenderer()
md = Markdown(rndr)


def backfill_images():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for resource in db.session.query(Resource).all():
        print("Backfilling image thumbnail for resource: {}".format(resource))
        body = StringIO(md(resource.body))
        tree = lxml.html.parse(body)
        images = tree.xpath("//img/@src")
        if images:
            print("Found image: {}".format(images[0]))
            resp = urlopen(images[0])
            image = upload_and_save_image(FileStorage(BytesIO(resp.read())))
            if image:
                resource.image_id = image.id
                db.session.commit()
                print("Successfully saved image...")
            else:
                print("Error saving image...")
        else:
            print("No image found...")

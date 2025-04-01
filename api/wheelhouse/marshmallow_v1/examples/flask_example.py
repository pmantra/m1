from datetime import datetime

from flask import Flask, jsonify, request
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from marshmallow_v1 import Schema, fields, ValidationError

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////tmp/quotes.db"
db = SQLAlchemy(app)

##### MODELS #####


class Author(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first = db.Column(db.String(80))
    last = db.Column(db.String(80))

    def __init__(self, first, last):
        self.first = first
        self.last = last


class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("author.id"))
    author = db.relationship("Author", backref=db.backref("quotes", lazy="dynamic"))
    posted_at = db.Column(db.DateTime)

    def __init__(self, content, author):
        self.author = author
        self.content = content
        self.posted_at = datetime.utcnow()


##### SCHEMAS #####


class AuthorSchema(Schema):
    formatted_name = fields.Method("format_name")

    def format_name(self, author):
        return "{}, {}".format(author.last, author.first)

    class Meta:
        fields = ("id", "first", "last", "formatted_name")


def must_not_be_blank(data):
    if not data:
        raise ValidationError("Data not provided.")


class QuoteSchema(Schema):
    author = fields.Nested(AuthorSchema, validate=must_not_be_blank)
    content = fields.Str(required=True, validate=must_not_be_blank)

    class Meta:
        fields = ("id", "content", "posted_at", "author")


author_schema = AuthorSchema()
quote_schema = QuoteSchema()
quotes_schema = QuoteSchema(many=True, only=("id", "content"))

##### API #####


@app.route("/api/v1/authors")
def get_authors():
    authors = Author.query.all()
    # Serialize the queryset
    serializer = AuthorSchema(many=True)
    result = serializer.dump(authors)
    return jsonify({"authors": result.data})


@app.route("/api/v1/authors/<int:pk>")
def get_author(pk):
    try:
        author = Author.query.get(pk)
    except IntegrityError:
        return jsonify({"message": "Author could not be found."}), 400
    author_result = author_schema.dump(author)
    quotes_result = quotes_schema.dump(author.quotes.all())
    return jsonify({"author": author_result.data, "quotes": quotes_result.data})


@app.route("/api/v1/quotes/", methods=["GET"])
def get_quotes():
    quotes = Quote.query.all()
    result = quotes_schema.dump(quotes)
    return jsonify({"quotes": result.data})


@app.route("/api/v1/quotes/<int:pk>")
def get_quote(pk):
    try:
        quote = Quote.query.get(pk)
    except IntegrityError:
        return jsonify({"message": "Quote could not be found."}), 400
    result = quote_schema.dump(quote)
    return jsonify({"quote": result.data})


@app.route("/api/v1/quotes/", methods=["POST"])
def new_quote():
    if not request.get_json():
        return jsonify({"message": "No input data provided"}), 400
    author_name = request.get_json().get("author")
    if author_name:
        first, last = author_name.split(" ")
        author_input = dict(first=first, last=last)
    else:
        author_input = {}
    content_input = request.get_json().get("content")
    input_data = dict(author=author_input, content=content_input)
    # Validate the input data
    errors = quote_schema.validate(input_data)
    if errors:
        return jsonify(errors), 400
    author = Author.query.filter_by(first=first, last=last).first()
    if author is None:
        # Create a new author
        author = Author(first, last)
        db.session.add(author)
    # Create new quote
    quote = Quote(content_input, author)
    db.session.add(quote)
    db.session.commit()
    result = quote_schema.dump(Quote.query.get(quote.id))
    return jsonify({"message": "Created new quote.", "quote": result.data})


if __name__ == "__main__":
    db.create_all()
    app.run(debug=True, port=5000)

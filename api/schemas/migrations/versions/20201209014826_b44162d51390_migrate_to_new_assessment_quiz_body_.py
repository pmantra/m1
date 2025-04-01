"""Migrate to new assessment quiz body export schema by topic.

Revision ID: b44162d51390
Revises: cd6b19a817f0
Create Date: 2020-12-09 01:48:26.574309

"""
import json

from storage.connection import db


# revision identifiers, used by Alembic.
revision = "b44162d51390"
down_revision = "cd6b19a817f0"
branch_labels = None
depends_on = None


def visit_export_objects(fn):
    quiz_bodies = db.session.execute("SELECT id, quiz_body FROM assessment;").fetchall()
    for aid, quiz_body in quiz_bodies:
        if not quiz_body:
            continue
        quiz_body = json.loads(quiz_body)
        questions = quiz_body and quiz_body.get("questions")
        if not isinstance(questions, list):
            continue
        for (
            question_index,  # noqa  B007  TODO:  Loop control variable 'question_index' not used within the loop body. If this is intended, start the name with an underscore.
            question,
        ) in enumerate(questions):
            # parse id:
            if "id" not in question:
                print("Could not establish exporter for question with no question id.")
                continue
            qid = question["id"]

            # parse export:
            if "export" not in question:
                continue
            export = question["export"]

            def update(new_export):
                print(
                    f"[updating export object] assessment_id={aid} question_id={qid} old_export={question['export']} new_export={new_export}"  # noqa  B023  TODO:  Function definition does not bind loop variable 'aid'.  'qid'. 'question'.
                )
                question[  # noqa  B023  TODO:  Function definition does not bind loop variable 'question'.
                    "export"
                ] = new_export
                db.session.execute(
                    "UPDATE assessment SET quiz_body=:quiz_body WHERE id=:id;",
                    params=dict(
                        id=aid,  # noqa  B023  TODO:  Function definition does not bind loop variable 'aid'.
                        quiz_body=json.dumps(
                            quiz_body  # noqa  B023  TODO:  Function definition does not bind loop variable 'quiz_body'.
                        ),
                    ),
                )
                db.session.commit()

            fn(export, update)


def upgrade():
    def treat_legacy_format_as_analytics(export, update):
        if "question_name" in export and "export_logic" in export:
            update({"ANALYTICS": export})

    visit_export_objects(treat_legacy_format_as_analytics)


def downgrade():
    def drop_non_analytics_export_topics(export, update):
        if "ANALYTICS" in export:
            update(export["ANALYTICS"])

    visit_export_objects(drop_non_analytics_export_topics)

"""Backfill sender field on CareAdvocateMemberTransitionTemplate model
"""
from enum import Enum
from string import Template

from docopt import docopt

from app import create_app
from care_advocates.models.transitions import (
    CareAdvocateMemberTransitionSender,
    CareAdvocateMemberTransitionTemplate,
)
from storage.connection import db


# Hardcoding message formats here becaues we need to start somewhere
class MessageFormats(Enum):
    FAREWELL = (
        CareAdvocateMemberTransitionSender.OLD_CX,
        Template(
            "Hi $MEMBER_FIRST_NAME,\n"
            "\n"
            "I hope you're doing well! I wanted to reach out to let you know that I'm transitioning out of this role at Maven. "
            "I'm so happy I had the privilege to be your Care Advocate, and I am sad to go "
            "but I'm leaving you in great hands! Your new Care Advocate will be $NEW_CX_FIRST_NAME - "
            "they are wonderful and will definitely be able to help you with any questions that arise.\n"
            "\n"
            "Wishing you the best,\n"
            "$OLD_CX_FIRST_NAME"
        ),
    )
    FOLLOWUP_INTRO = (
        CareAdvocateMemberTransitionSender.NEW_CX,
        Template(
            "Hi $MEMBER_FIRST_NAME,\n"
            "\n"
            "I hope you're doing well! My name is $NEW_CX_FIRST_NAME, and I will be your new "
            "Care Advocate on Maven, I'm so excited to be working with you!\n"
            "\n"
            "Let me know if there's anything you need support with at this time, I'm happy to direct you to the right "
            "resources!\n"
            "\n"
            "I look forward to hearing from you!\n"
            "\n"
            "Best,\n"
            "$NEW_CX_FIRST_NAME"
        ),
    )
    HARD_INTRO = (
        CareAdvocateMemberTransitionSender.NEW_CX,
        Template(
            "Hi $MEMBER_FIRST_NAME,\n"
            "\n"
            "I hope you're doing well! My name is $NEW_CX_FIRST_NAME, and I will be your new "
            "Care Advocate on Maven! $OLD_CX_FIRST_NAME has transitioned out of their role at Maven, so I'll "
            "be working with you for the rest of your time on Maven.\n"
            "\n"
            "Let me know if there's anything you need support with at this time, I'm happy to direct you to the right "
            "resources!\n"
            "\n"
            "I look forward to hearing from you!\n"
            "\n"
            "Best,\n"
            "$NEW_CX_FIRST_NAME"
        ),
    )
    SOFT_INTRO = (
        CareAdvocateMemberTransitionSender.NEW_CX,
        Template(
            "Hi $MEMBER_FIRST_NAME,\n"
            "\n"
            "I hope you're doing well! My name is $NEW_CX_FIRST_NAME, and I am your Care "
            "Advocate on Maven!\n"
            "\n"
            "Let me know if there's anything you need support with at this time, I'm happy to direct you to the right "
            "resources!\n"
            "\n"
            "I look forward to hearing from you!\n"
            "\n"
            "Best,\n"
            "$NEW_CX_FIRST_NAME"
        ),
    )
    ECPFAREWELL = (
        CareAdvocateMemberTransitionSender.OLD_CX,
        Template(
            "Hi $MEMBER_FIRST_NAME,\n"
            "\n"
            "It's $OLD_CX_FIRST_NAME here, thinking of you. I'm writing to check in. How are you doing? "
            "How are your appointments going on and off Maven?\n"
            "I'm also writing to share an update that I will be transitioning out of this role at Maven and won't be "
            "able to have appointments. It has been a great pleasure being on your pregnancy journey and being your "
            "resource thus far.\n"
            "\n"
            "With that in mind, your new Care Advocate will be added to your Care Team and will reach out to you "
            "shortly!\n"
            "\n"
            "Looking forward to hearing from you,\n"
            "$OLD_CX_FIRST_NAME\n"
            "Maven Care Team"
        ),
    )
    # https://www.merriam-webster.com/words-at-play/what-happens-to-names-when-we-make-them-plural-or-possessive
    FOLLOWUP_ECPINTRO = (
        CareAdvocateMemberTransitionSender.NEW_CX,
        Template(
            "Hi $MEMBER_FIRST_NAME,\n"
            "\n"
            "I hope this message finds you well. My name is $NEW_CX_FIRST_NAME and I'm another member on the Care Team. "
            "Given $OLD_CX_FIRST_NAME's last update about transitioning to a new team, I'm very excited to be your "
            "Care Advocate moving forward.\n"
            "\n"
            "I look forward to working together! If you have any questions please don't hesitate to reach out.\n"
            "\n"
            "Looking forward to hearing from you!\n"
            "\n"
            "Best,\n"
            "$NEW_CX_FIRST_NAME"
        ),
    )
    UCPFAREWELL = (
        CareAdvocateMemberTransitionSender.OLD_CX,
        Template(
            "Hi $MEMBER_FIRST_NAME,\n"
            "\n"
            "It's $OLD_CX_FIRST_NAME here, thinking of you. I'm writing to check in. How are you doing? "
            "How are your appointments going on and off Maven?\n"
            "\n"
            "I'm also writing to share an update that I will be transitioning out of this role at Maven. It has been a great "
            "pleasure being on your pregnancy journey and sharing resources with you thus far. I also wanted to let "
            "you know that another experienced Care Advocate will be added to your care team, to continue to be your "
            "source of support as you work towards the goals you've set on your care plan!\n"
            "\n"
            "All the best,\n"
            "$OLD_CX_FIRST_NAME\n"
            "Maven Care Team"
        ),
    )
    FOLLOWUP_UCPINTRO = (
        CareAdvocateMemberTransitionSender.NEW_CX,
        Template(
            "Hi $MEMBER_FIRST_NAME,\n"
            "\n"
            "I hope this message finds you well. My name is $NEW_CX_FIRST_NAME and I'm another member on the Care Team. "
            "I'm very excited to be your Care Advocate moving forward.\n"
            "\n"
            "I look forward to working together! If you have any questions please don't hesitate to reach out."
            "\n"
            "Looking forward to hearing from you!\n"
            "\n"
            "Best,\n"
            "$NEW_CX_FIRST_NAME\n"
        ),
    )


def _backfill_sender_field():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    message_format_name_to_tuple_map = {mf.name: mf.value for mf in MessageFormats}

    all_transition_templates = CareAdvocateMemberTransitionTemplate.query.all()

    backfill_count = 0
    for transition_template in all_transition_templates:
        (sender, __) = message_format_name_to_tuple_map.get(
            transition_template.message_type, (None, None)
        )

        if sender:
            transition_template.sender = sender
            db.session.add(transition_template)

            backfill_count += 1

    db.session.commit()
    print(f"*** Backfilled {backfill_count} transition templates ***")


def _rewind_backfill():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    all_transition_templates = CareAdvocateMemberTransitionTemplate.query.all()

    rewind_count = 0
    for transition_template in all_transition_templates:
        transition_template.sender = None
        db.session.add(transition_template)

        rewind_count += 1

    db.session.commit()
    print(f"*** Rewound {rewind_count} transition templates ***")


if __name__ == "__main__":
    args = docopt(__doc__)
    with create_app().app_context():
        if args.get("--rewind"):
            _rewind_backfill()
        else:
            _backfill_sender_field()

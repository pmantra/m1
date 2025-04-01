from appointments.utils.availability_requests import (
    get_member_availability_from_message,
)


def test_get_member_availability_from_message():
    message = "Hi Shelly,\n\n You have an appointment request!\n\nThe member’s availability is as follows (in order of preference):\n\nAug 30, 09:00AM-11:00AM, EDT\n\nIf any of these dates/times work for you, please open the corresponding availability. To coordinate a new time, you can reply directly to this message.\n\nNeed help? Reach out to providersupport@mavenclinic.com\n\nThank you!\n\nReference ID: 2"
    expected_avail = "\nAug 30, 09:00AM-11:00AM, EDT"
    actual_avail = get_member_availability_from_message(message)
    assert expected_avail == actual_avail

    message = "Hi Michael,\n\n You have an appointment request!\n\nThe member’s availability is as follows (in order of preference):\n\nAug 29, 09:00AM-11:00AM, EDT\nAug 30, 09:00AM-11:00AM, EDT\n\nIf any of these dates/times work for you, please open the corresponding availability. To coordinate a new time, you can reply directly to this message.\n\nNeed help? Reach out to providersupport@mavenclinic.com\n\nThank you!\n\nReference ID: 2"
    expected_avail = "\nAug 29, 09:00AM-11:00AM, EDT\nAug 30, 09:00AM-11:00AM, EDT"
    actual_avail = get_member_availability_from_message(message)
    assert expected_avail == actual_avail

    message = "Hi providername,\n\n You have an appointment request!\n\nThe member’s availability is as follows (in order of preference):\n\nAug 28, 08:00AM-06:00PM, EDT\nAug 29, 09:00AM-11:00AM, EDT\nAug 30, 09:00AM-11:00AM, EDT\n\nIf any of these dates/times work for you, please open the corresponding availability. To coordinate a new time, you can reply directly to this message.\n\nNeed help? Reach out to providersupport@mavenclinic.com\n\nThank you!\n\nReference ID: 2"
    expected_avail = "\nAug 28, 08:00AM-06:00PM, EDT\nAug 29, 09:00AM-11:00AM, EDT\nAug 30, 09:00AM-11:00AM, EDT"
    actual_avail = get_member_availability_from_message(message)
    assert expected_avail == actual_avail

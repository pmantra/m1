# Data Admin Files
The purpose of this is to create data admin json files in order to create test environments in local or qa environments

## create_staff.json
This json file can be used to create an user with admin access and to reset 2FA. You can upload this file to data admin 
and reset QR code. If you ever reset the database and would like to gain back access, you can upload this file to data 
admin with specifying an email of your choice in the "email": "your_email" section. Once you have uploaded this file, 
you can go to admin login page (for example: https://admin.qa2.mvnctl.net:444/admin/login) and login using this email 
and pw (the default password is "foo"). Then click get QR code and scan it using your phone. Once you have that, use 
that to log into admin. 

## eligibility_test_data.json
This json file can be used to test partner eligibility testing. User will be able to create organizations, organization 
employees, company_email, date_of_birth, beneficiaries_enabled, unique_corp_id, dependent_id, first_name, last_name, 
work_state, employee_only, medical_plan_only, alternate_verification etc.

## create_org_employee.json
This json file helps create an organization employee with a preset DOB. By uploading this file, you are creating new 
organization and new employee belong to that organization. You will need to sign up using the email provided or any 
email. Once you are logged in, you can use the DOB in this json file to verify employee account. 

## set_past_and_future_appointments.json
This json file helps create future and past appointments. You can create a new appointment, set the member and care team member email, and the start time of the appointment. Please change the emails and start time of the appointment for your use case. Requires 1 more CLI step to add the care team member to the appointment: `appointment.member.add_care_team_via_appointment(appointment)`. 

## set_practitioner_and_availability.json
This json file helps create a practitioner profile and set their availability. By using this file, you can create 
a practitioner who is certified in NY, can prescribe, allows anonymous, show when available enabled, messaging enabled.
Feel free to change the email in both email and practitioner field to create new ones. Make sure both email are exactly
same. You can update the date and time as you please. 

## send_message.json
This json file can be used to send a message between a member and practitioner. Using this json file,
you are able to create a member with email and pw and also a practitioner with email and pw who has messaging
enabled. Feel free to change email and pw for both member and practitioner. 

## set_user_on_pregnancy.json
This json file can be used to create an organization employee (of organization x) on pregnancy track. Once you upload 
this file, you will be able to just log in using this email with default pw "foo". You won't need to sign up. This sets the 
user to be on week 14. You can adjust the email and due days as you please. You need to make sure the organization
exists in admin. 

## set_user_on_postpartum.json
This json file can be used to create an organization employee (of organization x) on postpartum track. Once you upload 
this file, you will be able to just log in using this email with default pw "foo". You won't need to sign up. This sets the 
user to be on week 54. You can adjust the email and had_child_days_ago as you please. You need to make sure the organization
exists in admin. 

## set_user_with_pw.json
This json file can be used to create a marketplace user. After uploadiing this file to data admin
you will be to login using this email and pw. 

## set_message_for_users.json
This json file can be used to create five new users and five new practitioners and messages between them. In this
json file, the first user [test+mvnqamsgone@mavenclinic.com] has five messages to five different practitioners. This 
user also has one reply from first practitioner [test+qacarecoordinator@mavenclinic.com]. You can login using any of 
the email addresses (both user and practitioner) listed with default password `"foo"` and see the messages.

## create_forum_posts.json
This json file can be used to create forum posts in different category. You have to make sure the author of these posts
exists in the environment you are uploading. I have added a test user in this file. Uploading this file
should allow you to crate posts by this user in different categories. You may choose to change the `email`, `password`
and `authod` field as you like. 

## create_credit_for_new_user.json
This json file can be used to create credit for a new user. This is only applicable for creating a new user. 
You can change the email to your choice. The default pw for this user is `foo`. This will not work for an existing user. 

## test_enterprise_user.json
This is a test json file for an enterprise user scenario. This can be used to create an enterprise user. 
This will create appointments, messages, forum posts etc. This also creates a staff user at the bottom.
Please update the Email field at the bottom. 

## test_marketplace_user.json
This is a test json file for a marketplace user scenario. This can be used to create a marketplace user. 
This will create appointments, messages, forum posts etc. This also creates a staff user at the bottom.
Please update the Email field at the bottom.

## create_wallet_eligible_user.json
This is a test json file for an eligible wallet user who has not yet taken the survey but is eligible to have a wallet. 

## create_wallet_pending.json
This is a test json file that creates an eligible wallet user who has a pending wallet. 

## create_wallet_hra_reimbursement.json
This is a test json file that creates an eligible wallet user who has a qualified wallet with one reimbursement request 
that is state “REIMBURSED”. This will create a user in Alegeus (beta) if you are setup for it locally/QA2 
as well as the associated account (HRA in this case) but will not send the reimbursement request to Alegeus. 
Remember to update the company email if you need this to be compatible with e9y. 

## create_wallet_hdhp_reimbursement.json
This is a test json file that creates an eligible wallet user who has a qualified wallet with one reimbursement 
request that is in state “REIMBURSED”. This will create a user in Alegeus (beta) as well as the associated account 
(DTR in this case) if you are set up locally/QA2 but will not send the reimbursement request to Alegeus.
Remember to update the company email if you need this to be compatible with e9y. 

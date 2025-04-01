/*
    "dev": ["Maven-Okta", "saml-okta"],
    "qa1": ["Maven-Okta"],
    "qa2": [
        "Amazon",
        "Arkansas-BCBS",
        "CASTLIGHT",
        "Maven-Okta",
        "Optum-Mobile",
        "Optum-MSP",
        "Optum-Web",
        "PersonifyHealth",
        "Virgin-Pulse",
    ],
    "staging": ["Maven-Okta"],
    "prod": [
        "Arkansas-BCBS",
        "BonSecours",
        "CASTLIGHT",
        "Maven-OKTA-Test",
        "Optum-Mobile",
        "Optum-MSP",
        "Optum-Web",
        "PersonifyHealth",
        "Virgin-Pulse",
    ]
*/

exports.onExecutePostLogin = async (event, api) => {
    // Update below variables for different envs and launch phases.
    const softLaunch = true;
    const env = 'qa1';

    const connectionAllowList = ["Maven-Okta"];
    const homeUrlMap = {
        qa1: "https://www.qa1.mvnapp.net/",
        qa2: "https://www.qa2.mvnapp.net/",
        staging: "https://www.staging.mvnapp.net/",
        production: "https://www.mavenclinic.com/",
    };
    const homeUrl = homeUrlMap[env] || homeUrlMap["qa1"];
    const protocol = event.transaction?.protocol;

    const handleError = (userId, type) => {
        const errorMsg = `SAML identity mismatch detected! ${type} for ${userId}`;
        if (softLaunch) {
            console.log(errorMsg);
        } else {
            const redirectUrl = `${homeUrl}app/login?error=${encodeURIComponent(errorMsg)}`;
            api.redirect.sendUserTo(redirectUrl);
        }
    };

    if (protocol === 'samlp') {
        const connection = event.connection.name;
        console.log("SSO connection:" + connection);

        if (connectionAllowList.includes(connection)) {
            const user = event.user;
            const userId = user.user_id;
            const currentEmail = user.email;
            const currentFirstName = user.first_name;
            const currentLastName = user.last_name;
            const originalEmail = user.app_metadata?.original_email;
            const originalFirstName = user.app_metadata?.original_first_name;
            const originalLastName = user.app_metadata?.original_last_name;
            
            if (originalEmail == null || originalFirstName == null || originalLastName == null) {
                return; // Not backfilled yet, or first-time login
            }

            let emptyFields = [];
            let mismatchFields = [];

            if (originalEmail === "") emptyFields.push("Email");
            if (originalFirstName === "") emptyFields.push("First name");
            if (originalLastName === "") emptyFields.push("Last name");

            if (emptyFields.length > 0) {
                handleError(userId, `Empty value: ${emptyFields.join(", ")} connection ${connection}`);
            } else {
                if (currentEmail !== originalEmail) mismatchFields.push("Email");
                if (currentFirstName !== originalFirstName) mismatchFields.push("First name");
                if (currentLastName !== originalLastName) mismatchFields.push("Last name");

                if (mismatchFields.length > 0) {
                    handleError(userId, `Mismatch value: ${mismatchFields.join(", ")} connection ${connection}`);
                }
            }
        }
    }
};
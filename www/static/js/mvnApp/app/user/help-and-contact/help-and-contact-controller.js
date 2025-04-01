function HelpAndContactController() {}

angular.module("user").component("helpAndContact", {
	templateUrl: "/js/mvnApp/app/user/help-and-contact/index.html",
	controller: HelpAndContactController,
	bindings: {
		user: "<"
	}
})

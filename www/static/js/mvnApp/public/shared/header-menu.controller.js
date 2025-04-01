angular.module("publicpages").controller("HeaderMenuCtrl", [
	"$scope",
	"ngDialog",
	"MvnStorage",
	"$window",
	function ($scope, ngDialog, MvnStorage, $window) {
		var installParams = MvnStorage.getItem("local", "mvnInst")
				? JSON.parse(MvnStorage.getItem("local", "mvnInst"))
				: null,
			installAttrs = installParams ? installParams : {}

		$scope.openEntContact = function () {
			if ($window.location.pathname === "/404") {
				$window.location.href = "/"
				return
			}
			ngDialog.open({
				template: "/js/mvnApp/public/enterprise/_enterprise-contact.html",
				className: "mvndialog",
				scope: true,
				controller: [
					"$scope",
					function ($scope) {
						$scope.instParams = installAttrs
					}
				]
			})
		}
	}
])

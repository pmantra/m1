angular.module("app").factory("Agreements", [
	"$http",
	$http => ({
		sendAgreement: data => {
			return $http.post("/ajax/api/v1/_/agreements", data)
		}
	})
])

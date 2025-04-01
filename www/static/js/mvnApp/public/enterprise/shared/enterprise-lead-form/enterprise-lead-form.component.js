function EnterpriseLeadFormController($state, $timeout, $http) {
	const vm = this

	vm.send = function() {
		vm.loading = true

		const leadForm = {
			fields: [
				{
					name: "firstname",
					value: vm.firstname
				},
				{
					name: "lastname",
					value: vm.lastname
				},
				{
					name: "email",
					value: vm.email
				},
				{
					name: "company",
					value: vm.company
				},
				{
					name: "jobtitle",
					value: vm.jobtitle
				},
				{
					name: "numemployees",
					value: vm.numemployees
				}
			]
		}
		$http
			.post(
				`https://api.hsforms.com/submissions/v3/integration/submit/6390825/bb0b45de-5107-4601-887b-7b491948a106?pageUrl=${window.location.href}&pageName=${document.title}`,
				leadForm
			)
			.then(
				resp => {
					vm.loading = false
					$state.go("public.thank-you-demo-request")
				},
				error => {
					// WooOOoOooo hacky, FU angular.
					vm.timer = $timeout(() => {
						vm.error.message = true
						vm.loading = false
					}, 0)
				}
			)
	}

	vm.$onDestroy = () => {
		$timeout.cancel(vm.timer)
	}

	vm.$onInit = () => {
		vm.loading = false
		vm.error = {
			message: null
		}
	}
}

angular.module("publicpages").component("enterpriseLeadForm", {
	templateUrl: "/js/mvnApp/public/enterprise/shared/enterprise-lead-form/index.html",
	controller: EnterpriseLeadFormController,
	bindings: {
		error: "<"
	}
})

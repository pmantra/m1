function OnboardingAddressConfirmationController($rootScope, $state, Users, AppUtils, Plow) {
	const vm = this;

	vm.loading = true;
	vm.states = AppUtils.availableStates;

	const _getUserAddress = (uid) => {
		Users.getOrgEmployeeData(uid).get().then(a => {
			vm.userAddress = a;
			if (a) {
				vm.hasAddress = true;
				let evt = {
					"event_name" : "enterprise_onboarding_address_conf_has_address",
					"user_id": vm.user.id
				};
				Plow.send(evt);
			} else {
				vm.userAddress = {
					country: 'US'
				}
				let evt = {
					"event_name" : "enterprise_onboarding_address_no_address",
					"user_id": vm.user.id
				};
				Plow.send(evt);
			}
			vm.loading = false;
		}, e => {
			vm.loading = false;
			console.log('Error getting employee data...')
		})
	}

	const _completeAddressConf = () => {
		let evt = {
			"event_name" : "enterprise_onboarding_address_conf_complete",
			"user_id": vm.user.id
		};
		Plow.send(evt);
		$state.go('app.onboarding.customize-care-team-intro')
	}

	vm.$onInit = () => {
		Users.getWithProfile().then(u => {
			vm.user = u;
		})

		AppUtils.getCountries().then(c => {
			vm.countries = c;
		})

		let progress = {
			percentage: 35
		}
		vm.updateProgress()(progress)

		_getUserAddress(vm.user.id)
	}

	vm.saveAddress = (a) => {
		vm.loading = true;

		const newAddr = {
			street_address: a.address_1 + ' ' + a.address_2,
			city: a.city,
			zip_code: a.zip_code,
			state: a.state,
			country: a.country
		}

		vm.user.profiles.member.address = newAddr;
		vm.user.profiles.member.state = a.country === 'US' ? a.state : 'ZZ';

		Users.updateUserProfile(vm.user.id, vm.user.profiles.member).then(u => {
			$rootScope.user = vm.user;
			$rootScope.$broadcast('updateUser', vm.user);
			vm.updateUser();
			_completeAddressConf()
		})
		.catch(e => {
			vm.loading = false
			console.log(e)
		})
	}

	vm.tagHandler = function (tag) { // this is a ridic hack to fix ui-select bug... see https://github.com/angular-ui/ui-select/issues/1355#issuecomment-213058279
		return null;
	}

	vm.skipAddress = () => {
		let evt = {
			"event_name" : "enterprise_onboarding_skip_address_conf",
			"user_id": vm.user.id
		};
		Plow.send(evt);
		$state.go('app.onboarding.customize-care-team-intro')
	}

}

angular.module('app').component('onboardingAddressConfirmation', {
	templateUrl: 'js/mvnApp/app/user/onboarding/enterprise/_onboarding-address-confirmation.html',
	controller: OnboardingAddressConfirmationController,
	bindings: {
		user: '<',
		updateProgress: '&',
		updateUser: '&'
	}
})
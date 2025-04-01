function EnterpriseClaimInviteController($state, Users, Plow) {
	const vm = this;
	
	vm.registerWithInvite = () => {
		let evt= {
			"event_name": "web_go_to_register_with_invite"
		}
		Plow.send(evt);

		$state.go('auth.localregister', {"claiminvite": $state.params.claiminvite})
	}

	vm.$onInit = function () {
		vm.loading = true;
		if (!$state.params.claiminvite) {
			vm.badInvite = true;
			vm.loading = false;
		} else {
			Users.getInvite($state.params.claiminvite).then(i => { 
				vm.invitee = {
					name: i.name,
					module: i.module
				}
				vm.loading = false;
			}, e => {
				//TODO
				vm.badInvite = true;
				vm.loading = false;
			})

			vm.loading = false;
		}
		
		
	}

	
}

angular.module('publicpages').component('enterpriseClaimInvite', {
	templateUrl: 'js/mvnApp/public/enterprise/_enterprise-claim-invite.html',
	controller: EnterpriseClaimInviteController,
	bindings: {
		user: '<'
	}
});
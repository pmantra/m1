function OnboardingChildBirthdayController($state, Plow, AppUtils, Healthbinder) {
	const vm = this;

	vm.$onInit = () => {
		vm.noDatePicker = !Modernizr.inputtypes.date;

		vm.dateToday = AppUtils.removeTimeZone(moment());
		vm.userState = $state.params;
		let progress = {
			percentage: 15
		}
		vm.updateProgress()(progress)
	}

	vm.setBabyInfo = (baby) => {
		// ADD CHILD
		vm.babyBday = new Date(baby.birthday);
		vm.babyName = baby.name;
		vm.yearNow = moment().year();
	}

	vm.selectBabyBirthDate = (date, doMerge) => {
		var theDate;

		if (doMerge) {
			theDate = AppUtils.mergeDate(date);
		} else {
			theDate = date;
		}
		if (moment(theDate).diff( moment(vm.dateToday) ) <= 0 ) {
			vm.selectedDay = date;
			vm.setBabyInfo({ 'birthday' : theDate })
		}
	}

	vm.saveBabyInfo = (dob, name) => {
		var bbName = name ? name : 'child';
		var bdayUpdate = {
			'birthday': moment(vm.babyBday).format('YYYY-MM-DDTHH:mm:ss'),
			'name': bbName
		}
		Healthbinder.updateChild(vm.user.id, bdayUpdate).then(function(h) {
			$state.go('app.onboarding.verify-enterprise', vm.userState);
			let evt = {
				"event_name" : "enterprise_onboarding_save_baby_birthday",
				"user_id": vm.user.id
			};
			Plow.send(evt);
		});

		vm.setBabyInfo( {
			'birthday' : moment(bdayUpdate.birthday).utc(),
			'name' : bdayUpdate.name
			}
		);
	}


}

angular.module('app').component('onboardingChildBirthday', {
	templateUrl: 'js/mvnApp/app/user/onboarding/lifestages/2.html',
	controller: OnboardingChildBirthdayController,
	bindings: {
		user: '<',
		updateProgress: '&'
	}
});
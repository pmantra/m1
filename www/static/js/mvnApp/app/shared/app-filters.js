angular.module('app').filter('minzero', function() {
	return function(input) {
		return (input >= 0) ? input : 0;
	};
});

angular.module('app').filter('capitalize', function() {
	return function(input, all) {
		var reg = (all) ? /([^\W_]+[^\s-]*) */g : /([^\W_]+[^\s-]*)/;
		return (!!input) ? input.replace(reg, function(txt){return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();}) : '';
	}
});

angular.module('app').filter('positive', function() {
	return function(input) {
		if (!input) {
			return 0;
		}

	return Math.abs(input);
	};
})

angular.module('app').filter('filterBySection', function() {
	return function(input, item) {
		return _.filter(input, function(o) { return o.value === item; });
	}
});

angular.module('app').filter('commaSeparate', function() {
	return function(input) {
		return input.replace(/\,/g,", ");// eslint-disable-line no-useless-escape
	};
});

angular.module('app').filter('apptPurpose', function () {
	var apptPurpose;
	return function (input) {
		switch (input) {
			case 'birth_needs_assessment':
				apptPurpose = 'Pregnancy Needs Assessment'
				break;
			case 'postpartum_needs_assessment':
				apptPurpose = 'Postpartum Needs Assessment'
				break;
			case 'introduction':
				apptPurpose = 'Introductory appointment'
				break;
			case 'birth_planning':
				apptPurpose = 'Birth Planning Appointment'
				break;
			case 'introduction_egg_freezing':
				apptPurpose = 'Introduction (Egg Freezing)'
				break;
			case 'introduction_fertility':
				apptPurpose = 'Introduction (Fertility)'
				break;
			case 'introduction_adoption':
				apptPurpose = 'Introduction (Adoption)'
				break;
			case 'introduction_surrogacy':
				apptPurpose = 'Introduction (Surrogacy)'
				break;
			case 'introduction_pregnancyloss':
				apptPurpose = 'Introduction (Pregnancy loss)'
				break;
			//default:
			//	return 'Introductory appointment'

		}
		return apptPurpose;
	};
});

angular.module('app').filter('secondsToMinutes', [function () {
	return function (seconds) {
		return seconds / 60;
	};
}])

angular.module('app').filter('stateCodeToName', ['AppUtils', function (AppUtils) {
	return function (stateCode) {
		let getState = AppUtils.availableStates.find(s => s.code === stateCode);
		return getState ? getState.name : null;
	};
}])


angular.module('app').filter('countryCodeToName', [ function () {
	return function (countryCode, countryList) {
		let getCountry = countryList.find(c => c.alpha_2 === countryCode);
		return getCountry ? getCountry.name : null;
	};
}])

angular.module('app').filter('pracNetworkAbbrevToName', ['AppUtils', function (AppUtils) {
	return function (networkAbbrev) {
		if (!networkAbbrev) {
			return
		} else {
			let getName = AppUtils.pracNetworkTypes.find(s => s.type === networkAbbrev);
			return getName ? getName.name : null;
		}
	};
}])

angular.module('app').filter('telNumberFormat', function() {
	return function(input) {
		if (!input) {
			return 'not set';
		}

		if (window.intlTelInputUtils) {
			if (input.split(':')[0] === 'tel') {
				input = input.split(':')[1]
			}
			return window.intlTelInputUtils.formatNumber(input, null, window.intlTelInputUtils.numberFormat.NATIONAL);
		} else  {
			return input;
		}
	};
})
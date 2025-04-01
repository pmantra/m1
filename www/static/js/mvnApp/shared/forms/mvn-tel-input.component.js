

angular.module('app').directive('mvnTelInput', [function() {
	return {
		link: function(scope, elem, attrs) {
			scope.isRequired = ('required' in attrs) && attrs.required !== "false"
		},
		controller: function($scope) {
			const vm = this

			if ($scope.value && $scope.value.split(':')[0] === 'tel') {
				$scope.value = $scope.value.split(':')[1]
			}

			vm.inheritedOnChange = () => {
				// ()() because this onChange is a fn that returns another fn (the passed onChange). You can avoid this by binding onChange with `=`, but that's cheating so we'll stick with `&` and ()()
				if ($scope.onChange()) $scope.onChange()()
			}
		},
		controllerAs: 'mvnInputCtrl',
		templateUrl: '/js/mvnApp/shared/forms/templates/_tel-input.html',
		scope: {
			formRef: '<',
			label: '@',
			maxlength: '@',
			minlength: '@',
			placeholder: '@',
			type: '@',
			value: '=',
			onChange: '&'
		}
	}
}])
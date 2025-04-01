angular.module("app").directive("mvnInput", [
	function() {
		return {
			link: function(scope, elem, attrs) {
				scope.isRequired = "required" in attrs && attrs.required !== "false"
			},
			controller: function($scope) {
				const vm = this
				vm.inheritedOnChange = () => {
					// ()() because this onChange is a fn that returns another fn (the passed onChange). You can avoid this by binding onChange with `=`, but that's cheating so we'll stick with `&` and ()()
					if ($scope.onChange()) $scope.onChange()()
				}
			},
			controllerAs: "mvnInputCtrl",
			templateUrl: "/js/mvnApp/shared/forms/templates/_mvn-input.html",
			scope: {
				formRef: "<",
				label: "@",
				maxlength: "@",
				minlength: "@",
				placeholder: "@",
				type: "@",
				value: "=",
				onChange: "&",
				max: "@",
				min: "@",
				pattern: "@",
				arialabel: "@"
			}
		}
	}
])

angular.module("app").directive("mvnTextArea", [
	function() {
		return {
			link: function(scope, elem, attrs) {
				scope.isRequired = "required" in attrs && attrs.required !== "false"
				scope.textareaid = attrs.textareaid
			},
			controller: function($scope) {
				const vm = this
				vm.inheritedOnChange = () => {
					// ()() because this onChange is a fn that returns another fn (the passed onChange). You can avoid this by binding onChange with `=`, but that's cheating so we'll stick with `&` and ()()
					if ($scope.onChange()) $scope.onChange()()
				}
			},
			controllerAs: "mvnInputCtrl",
			templateUrl: "/js/mvnApp/shared/forms/templates/_text-area.html",
			scope: {
				label: "@",
				value: "=",
				placeholder: "@",
				onChange: "&"
			}
		}
	}
])

angular.module("app").directive("mvnCheckboxGroup", [
	function() {
		return {
			controller: function($scope) {
				var vm = this

				if ($scope.modelRef) {
					// String to object
					var modelArray = $scope.modelRef.split(",")
					vm.modelRefCopy = modelArray.reduce(function(modelObj, val) {
						modelObj[val] = true
						return modelObj
					}, {})
				} else {
					vm.modelRefCopy = {}
				}

				vm.updateSelection = function() {
					var keys = Object.keys(vm.modelRefCopy)
					var selectedValues = keys.filter(function(key) {
						return vm.modelRefCopy[key]
					})
					$scope.modelRef = selectedValues.join()
				}
			},
			controllerAs: "mvnCheckboxGroupCtrl",
			templateUrl: "/js/mvnApp/shared/forms/templates/_checkbox-group.html",
			scope: {
				type: "@",
				label: "@",
				options: "=",
				modelRef: "="
			}
		}
	}
])

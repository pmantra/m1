angular.module("app").directive("mvnMergedInput", [
	function() {
		return {
			link: function(scope, elem, attrs) {
				elem.bind("click", function(e) {
					var firstInput = elem[0].querySelector(".merge-field")
					if (firstInput !== null) {
						firstInput.focus()
					}
				})
			},
			restrict: "E",
			transclude: true,
			scope: {
				modelRef: "=",
				mergeFn: "&",
				updateFn: "&",
				formRef: "<",
				label: "@"
			},
			templateUrl: "/js/mvnApp/shared/forms/templates/_merged-input.html",
			controllerAs: "mergedInputCtrl",
			controller: function($scope) {
				var mergedInputCtrl = this

				mergedInputCtrl.handleBlur = function() {
					_.delay(function() {
						if (!mergedInputCtrl.isActive) $scope.$parent.$ctrl.hasBeenBlurred = true
					}, 100)

					if (!mergedInputCtrl.isActive) {
						$scope.$parent.$ctrl.handleBlur()
						$scope.$apply()
					}
				}

				mergedInputCtrl.updateInput = function() {
					$scope.updateFn()

					// No need to show an error message during a user's first interaction with an input/while a user is still interacting with it
					if ($scope.$parent.$ctrl.hasBeenBlurred) $scope.$apply()
				}
			}
		}
	}
])

angular.module("app").directive("mvnMergeField", [
	function() {
		return {
			restrict: "E",
			require: "^?mvnMergedInput",
			scope: {
				max: "@",
				min: "@",
				maxlength: "@",
				minlength: "@",
				name: "@",
				pattern: "@",
				placeholder: "@",
				type: "@",
				value: "=",
				onChange: "&",
				arialabel: "@"
			},
			templateUrl: "/js/mvnApp/shared/forms/templates/_merge-field.html",
			link: function(scope, elem, attrs, mergedInputCtrl) {
				elem.bind("click", function(e) {
					e.stopPropagation()
				})

				// passing a string to ng-pattern doesn't work, so turn pattern into a RegExp
				scope.patternRegex = new RegExp(scope.pattern)
				scope.isRequired = "required" in attrs && attrs.required !== "false"

				scope.focusInput = function() {
					mergedInputCtrl.isActive = true
				}

				scope.blurInput = function() {
					mergedInputCtrl.isActive = false
					_.delay(mergedInputCtrl.handleBlur, 100)
				}

				// debounce here instead of using ng-model-options to get around issues with ng-change firing before the model updates
				scope.debouncedUpdate = _.debounce(mergedInputCtrl.updateInput, 200, { leading: false, trailing: true })

				scope.updateMergedInput = () => {
					scope.debouncedUpdate()

					// ()() because this onChange is a fn that returns another fn (the passed onChange). You can avoid this by binding onChange with `=`, but that's cheating so we'll stick with `&` and ()()
					if (scope.onChange()) scope.onChange()()

					//console.log(scope, 'mergeedinput debounce update');
				}
			}
		}
	}
])

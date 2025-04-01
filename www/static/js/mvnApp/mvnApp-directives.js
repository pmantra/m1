/*
 *
 * Main Directives
 *
 *
 */

angular.module("mavenApp").directive("mvnSkipToContent", [
	function() {
		return {
			restrict: "A",
			link: function(scope, element, attrs) {
				let doFocus = e => {
					e.preventDefault()
					let focusElem = document.getElementsByClassName("main-content-area")[0]
					if (focusElem !== null) {
						focusElem.focus()
					}
				}
				element.bind("click", doFocus)
			}
		}
	}
])

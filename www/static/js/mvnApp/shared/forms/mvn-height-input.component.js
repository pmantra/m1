function HeightInputController() {
	var vm = this
	
	vm.$onInit = function() {
		if (vm.modelRef) {
			vm.hasContent = true
			vm.parsedHeight = {
				ft: parseInt(vm.modelRef / 12),
				in: vm.modelRef % 12
			}
		} else {
			vm.defaults = {
				ft: undefined,
				in: undefined
			}
			vm.parsedHeight = vm.defaults
		}
		
		vm.inputKeys = _.keys(vm.parsedHeight)
		vm.hasBeenBlurred = false
	}
	
	vm.checkContent = function() {
		vm.inputValues = _.values(vm.parsedHeight)
		vm.hasContent = _.some(vm.inputValues, function(val) { return typeof val === "number" })
		vm.isFilled = _.every(vm.inputValues, function(val) { return val >= 0 })
	}
	
	vm.flagMissingContent = function() {
		_.each(vm.inputKeys, function(key) {
			vm.formRef[key].$setValidity('missing', typeof vm.parsedHeight[key] === "number")
		})
	}
	
	vm.isIncomplete = function() {
		if (vm.hasContent) vm.flagMissingContent()
		return vm.hasContent && !vm.isFilled
	}

	vm.isInvalid = function(vals) {
		vm.hasInputErrors = _.some(vm.inputKeys, function(key) {
			return vm.formRef[key].$invalid
		})
		
		var editedAndInvalid = vm.formRef.$dirty && vm.hasContent && vm.hasInputErrors
		
		return editedAndInvalid
	}
	
	vm.checkForErrors = function() {
		vm.hasErrors = vm.isIncomplete() || vm.isInvalid()
		// If user clears the input
		if (!vm.hasContent) {
			vm.clearErrors()
			vm.modelRef = vm.defaults
		}
	}
	
	vm.clearErrors = function() {
		// User shouldn't see "missing" error messages if they clear all fields
		_.each(vm.inputKeys, function(key) {
			vm.formRef[key].$error = {}
		})
	}
	
	vm.handleBlur = function() {
		vm.checkContent()
		vm.checkForErrors()
	}
	
	vm.updateInput = function() {
		vm.checkContent()
		if (vm.hasBeenBlurred) vm.checkForErrors()
		if (vm.isFilled && !vm.hasErrors) vm.heightToInches(vm.inputValues)
	}
	
	vm.heightToInches = function() {
		vm.modelRef = (vm.parsedHeight.ft * 12) + vm.parsedHeight.in
	}
}

angular.module('app').component('mvnHeightInput', {
	controller: HeightInputController,
	templateUrl: '/js/mvnApp/shared/forms/templates/_height-input.html', 
	bindings: {
		formRef: '<',
		modelRef: '=',
		label: '@',
		onChange: '&'
	}
})
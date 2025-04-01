function DateInputController() {
	var vm = this

	vm.$onInit = function() {
		if (vm.modelRef) {
			vm.hasContent = true
			vm.parsedDate = {
				year: moment(vm.modelRef).format('YYYY'),
				month: moment(vm.modelRef).format('MM'),
				day: moment(vm.modelRef).format('DD'),
			}
		} else {
			vm.defaults = {
				year: '',
				month: '',
				day: ''
			}

			vm.parsedDate = vm.defaults
		}

		vm.inputKeys = _.keys(vm.parsedDate)
		vm.hasBeenBlurred = false
	}

	vm.checkContent = function() {
		vm.inputValues = _.values(vm.parsedDate)
		vm.hasContent = _.some(vm.inputValues, function(val) { return !!val })
		vm.isFilled = _.every(vm.inputValues, function(val) { return !!val })
	}

	vm.flagMissingContent = function() {
		_.each(vm.inputKeys, function(key) {
			vm.formRef[key].$setValidity('missing', !!vm.parsedDate[key])
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
		if (vm.isFilled && !vm.hasErrors) vm.formatDateString(vm.inputValues)
	}

	vm.formatDateString = function(vals) {
		var dateString = vals.join('-')
		vm.modelRef = moment(dateString, 'YYYY-MM-DD').format('YYYY-MM-DD')

	}

}

angular.module('app').component('mvnDateInput', {
	controller: DateInputController,
	templateUrl: '/js/mvnApp/shared/forms/templates/_date-input.html',
	bindings: {
		formRef: '<',
		modelRef: '=',
		label: '@',
		required: '<'
	}
})
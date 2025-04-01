function btwSliderController() {
	var vm = this

	vm.formatDollarAmount = function(num) {
		return num.toLocaleString('en-US', { style: 'decimal', currency: 'USD' })
	}

	vm.updateValue = function(val) {
		vm.calculatedValue = vm.formatDollarAmount(val * vm.costPerMom)
		vm.fontSize = 2 + (val / 15000)
	}

	// Defaults
	vm.costPerMom = 91800
	vm.sliderValue = 100
	vm.sliderMin = 20
	vm.sliderMax = 5000
	vm.calculatedValue = vm.formatDollarAmount(vm.sliderValue * vm.costPerMom)
	vm.fontSize = '2'
}

angular.module('publicpages')
	.component('btwSlider', {
		templateUrl: '/js/mvnApp/public/enterprise/shared/_slider-component.html',
		controller: btwSliderController,
	});

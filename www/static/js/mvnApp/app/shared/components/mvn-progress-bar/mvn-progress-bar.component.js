
/* Progress Bar */

angular.module('app').component('mvnProgressBar', {
	template: `
		<div class="progress-bar {{ $ctrl.barClass }}">
			<div class="bar-full">
				<div ng-if="!$ctrl.timed"  class="bar-progress {{ $ctrl.progressClass }}" ng-style="{ width: $ctrl.progress + '%'}"></div>
				<div ng-if="$ctrl.timed" class="bar-progress primary prog-bar-animate" ng-style="{ animationDuration : $ctrl.timed + 'ms' }"></div>
			</div>
		</div>
	`,
	bindings: {
		progress: '=',
		barClass: '@',
		progressClass: '@',
		timed: '@'
	}
});


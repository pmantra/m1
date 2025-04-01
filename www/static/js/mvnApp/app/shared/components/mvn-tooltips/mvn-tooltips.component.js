angular.module("app").component("mvnTooltip", {
	template: `
    <div class="tooltip">
      <div><img src="/img/app/shared/tooltip.png" alt="tooltip icon" /></div>
      <p>
        <span><strong>{{ $ctrl.hed }} - </strong></span>
        {{ $ctrl.dek }}
      </p>
		</div>
	`,
	bindings: {
		hed: "@",
		dek: "@"
	}
})

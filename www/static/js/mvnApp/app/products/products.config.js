/* Purchasable products in-app */

angular.module('products').config([
	'$stateProvider',
	function($stateProvider) {
		$stateProvider.state('app.products', {
			abstract: true,
			bodyClass: 'page-products',
			template: `
			<section class="app-page">
				<main class="single-panel">
						<div class="">
							<ui-view />
						</div>
					</main>
			</section>`
		})

		$stateProvider.state('app.products.bms', {
			url: '/products/maven-milk',
			react: true
		})
	}
])

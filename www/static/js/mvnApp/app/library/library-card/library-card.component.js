function LibraryCardController(Plow) {
	const vm = this

	vm.$onInit = () => {
		_formatContentType()
		_getUrl()
		vm.templateUrl = `/js/mvnApp/app/library/library-card/${vm.featured ? "_featured" : "index"}.html`
	}

	vm.sendEvt = () => {
		const evt = {
			event_name: "ent_lib_click",
			assessment_id: vm.cardData.assessment_id,
			resource_id: vm.cardData.resource_id,
			position: !!vm.featured ? 0 : vm.position + 1
		}

		Plow.send(evt)
	}

	const _formatContentType = () => {
		vm.cardData.prettyContentType = vm.cardData.content_type.replace(/\_/g, " ") // eslint-disable-line  no-useless-escape
	}

	const _getUrl = () => {
		const isQuiz = !!vm.cardData.assessment_id
		const isPublicResource = !!vm.cardData.slug
		let resUrl

		if (isQuiz) {
			resUrl = `app.assessments.one.view({ id: ${vm.cardData.assessment_id}, slug: '${vm.cardData.slug}' })`
		} else if (isPublicResource) {
			resUrl = `app.resources.enterprise.public({ type: '${vm.cardData.content_type}', resourceId: '${
				vm.cardData.slug
			}' })`
		} else {
			resUrl = `app.resources.enterprise.private({ resourceId: ${vm.cardData.id} })`
		}

		vm.resourceUrl = resUrl
	}
}

angular.module("app").component("libraryCard", {
	bindings: {
		cardData: "<",
		featured: "@",
		position: "<"
	},
	controller: LibraryCardController,
	template: '<div ng-include="$ctrl.templateUrl" class="list-item-container"></div>'
})

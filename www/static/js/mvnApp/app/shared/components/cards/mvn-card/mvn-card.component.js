function MvnCardController($state, ModalService, Plow) {
	const vm = this
	
	vm.$onInit = () => {
		const hasLimitedSpace = ['list-item', 'visual-content'].includes(vm.data.type)
		if (hasLimitedSpace && vm.data.body[0]) _truncateBody()
	}
	
	const _concatString = (string, n) => {
		return `${string.substring(0, n)}...`
	}
	
	const _truncateBody = () => {
		// limit content to one paragraph for now
		let characterLimit
		switch (vm.data.type) {
			case 'list-item':
				characterLimit = 50
				break
			case 'visual-content':
				characterLimit = 150
				break
			default:	
				return
		}
		
		vm.data.body = [_concatString(vm.data.body[0], characterLimit)]
		return 
	}
}

angular.module('app').component('mvnCard', {
	templateUrl: '/js/mvnApp/app/shared/components/cards/mvn-card/_card.html',
	controller: MvnCardController,
	bindings: {
		data: '=',
		user: '='
	}
})

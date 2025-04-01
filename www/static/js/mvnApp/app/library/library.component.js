function LibraryController($http, $q, config, Library, Users) {
	const vm = this;
	
	vm.$onInit = function() {
		
		$q.all([getUser, getTags]).then(res => {
			vm.user = res[0]
			vm.categories = res[1]
			
			const structuredPrograms = vm.user.structured_programs[0]
			const moduleName = structuredPrograms.current_module
			const moduleId = structuredPrograms.current_module_id
			const phaseId = structuredPrograms.modules[moduleName].current_phase.phase_id
			
			getResources(moduleId, phaseId)
		})
		
		_setUpTypeNames()
	}
	
	const getUser = Users.getWithProfile().then(u => (u))
	const getTags = Library.getTags().then(t => (t))
	const getResources = (moduleId, phaseId) => {
		const req = {
			module_id: moduleId,
			phase_id: phaseId, 
			limit: 5
		}
		Library.getResources(req).then(res => {
			vm.resources = res.plain()
			_getFeaturedCard()
		})
	}
	
	const _setUpTypeNames = () => {
		const typeDisplayNames = {
			'quiz': 'Quizzes',
			'article': 'Articles',
			'ask_a_practitioner': 'Ask a Practitioner',
			'real_talk': 'Real Talks'
		}
		vm.contentTypes = config.content_types
		vm.contentTypes.forEach(type => {
			type.display_name = typeDisplayNames[type.name]
		})
	}
	
	const _getFeaturedCard = () => {
		vm.featuredCard = vm.resources.find(resource => (!!resource.image && !!resource.image.hero))
		vm.resources.splice(vm.resources.indexOf(vm.featuredCard), 1)
	}
}

angular.module('app').component('library', {
	templateUrl: '/js/mvnApp/app/library/index.html',
	controller: LibraryController
});
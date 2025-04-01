function LibraryFilteredPageController($state, Users, Library) {
	const vm = this;
	let pageLimit = 20;
	let pageStart = 0;
	let allLoaded = false;

	vm.$onInit = function() {
		Users.getWithProfile().then(u => {
			vm.user = u;
			vm.topic = $state.params.topic;
			vm.type = $state.params.type;
			vm.pageTitle =
				(vm.topic && $state.params.displayName) ||
				_getPageTitle(vm.topic, vm.type);

			initializeResources();
		});
	};

	vm.loadMore = () => {
		if (!vm.loadingMore) getMoreResources();
	};

	const initializeResources = () => {
		const onComplete = res => {
			vm.resources = res;
			_getFeaturedCard();
		};
		getResources(onComplete);
	};

	const getMoreResources = () => {
		if (!allLoaded) {
			vm.loadingMore = true;
			pageStart += pageLimit;
			const onComplete = res => {
				if (res) {
					res.forEach(r => {
						vm.resources.push(r);
					});
				}
				vm.loadingMore = false;
			};

			getResources(onComplete);
		}
	};

	const getResources = onComplete => {
		const req = {
			tags: vm.topic,
			content_types: vm.type,
			limit: pageLimit,
			offset: pageStart
		};

		Library.getResources(req).then(res => {
			if (res[0]) {
				onComplete(res);
			} else {
				allLoaded = true;
				vm.loadingMore = false;
			}
		});
	};

	const _getPageTitle = (topic, type) => {
		if (topic) {
			Library.getTags().then(tags => {
				vm.pageTitle = tags.filter(tag =>
					[topic, type].includes(tag.name)
				)[0].display_name;
			});
		} else {
			const typeDisplayNames = {
				quiz: "Quizzes",
				article: "Articles",
				ask_a_practitioner: "Ask a Practitioner",
				real_talk: "Real Talks"
			};

			return typeDisplayNames[type];
		}
	};

	const _getFeaturedCard = () => {
		vm.featuredCard = vm.resources.find(
			resource => !!resource.image && !!resource.image.hero
		);
		vm.resources.splice(vm.resources.indexOf(vm.featuredCard), 1);
	};
}

angular.module("app").component("libraryFilteredPage", {
	templateUrl: "/js/mvnApp/app/library/library-filtered-page/index.html",
	controller: LibraryFilteredPageController
});

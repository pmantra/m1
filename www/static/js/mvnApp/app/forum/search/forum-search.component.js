function ForumSearchResultsController($state, Posts, Plow) {
	var vm = this,
		req,
		evt,
		orderBy = "created_at";
	vm.pageLimit = 10;
	vm.pageStart = 0;

	var getPosts = function(req, onComplete) {
		Posts.getPosts()
			.getList(req)
			.then(function(posts) {
				vm.totalPosts = posts.pagination.total;
				onComplete(posts);

				evt = {
					event_name: "forum_search_results",
					query: vm.q,
					user_id: vm.user ? String(vm.user.id) : '',
					results_count: String(vm.totalPosts)
				};

				Plow.send(evt);
			});
	};

	var gotMorePosts = function(posts) {
		angular.forEach(posts, function(post) {
			vm.posts.push(post);
		});
		vm.loadingMore = false;
	};

	vm.loadMore = function() {
		if (!vm.loadingMore) {
			// DON'T load more if we're already loading and waiting for the results...
			vm.pageStart = vm.pageStart + vm.pageLimit;
			if (vm.totalPosts >= vm.pageStart) {
				vm.loadingMore = true;
				req = {
					depth: 0,
					keywords: $state.params.q,
					limit: vm.pageLimit,
					offset: vm.pageStart,
					order_by: orderBy
				};
				getPosts(req, gotMorePosts);
			} else {
				return false;
			}
		}
	};

	vm.$onInit = function() {
		vm.loading = true;
		vm.q =
			$state.params.q && $state.params.q.length > 1 ? $state.params.q : null;
		if (vm.q) {
			req = {
				depth: 0,
				keywords: $state.params.q,
				limit: vm.pageLimit,
				offset: vm.pageStart,
				order_by: orderBy
			};
			var onComplete = function(posts) {
				vm.posts = posts;
				vm.loading = false;
			};
			getPosts(req, onComplete);
		} else {
			vm.loading = false;
		}
	};
}

angular.module("forum").component("forumSearchResults", {
	templateUrl: "/js/mvnApp/app/forum/search/index.html",
	controller: ForumSearchResultsController,
	bindings: {
		user: "<",
		cats: "<",
		showSearchMenu: "="
	}
});

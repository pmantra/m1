function ForumPopularPostsController(Posts) {
	var vm = this,
		req

	var _getPosts = function() {
		req = { depth: 0, limit: vm.show, offset: 0, order_by: "popular", include_profile: true }

		if (vm.cat) {
			req.categories = vm.cat.name
		}

		Posts.getPosts()
			.getList(req)
			.then(function(posts) {
				vm.posts = posts
				vm.loading = false
			})
	}

	vm.setLoaders = function(num) {
		return new Array(num)
	}

	vm.$onInit = function() {
		vm.loading = true
		_getPosts()
	}
}
angular.module("forum").component("forumPopularPosts", {
	templateUrl: "/js/mvnApp/app/forum/common/popular-posts/_forum-popular-posts.html",
	controller: ForumPopularPostsController,
	bindings: {
		cat: "<",
		show: "<",
		cats: "<",
		user: "<"
	}
})

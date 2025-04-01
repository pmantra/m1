function ForumPostDetailController($state, Posts, Plow, SeoService) {
	var vm = this,
		evt

	var postID = $state.params.post_id

	var _getPost = function() {
		Posts.getPost(postID)
			.get()
			.then(function(post) {
				vm.post = post

				// Set page title now we have it
				SeoService.setPageTitle({
					title: vm.post.title
				})

				// Track
				evt = {
					event_name: "forum_detail",
					user_id: vm.user ? String(vm.user.id) : '',
					post_id: String(vm.post.id),
					practitioner_responses: String(post.reply_counts.practitioners),
					member_responses: String(post.reply_counts.members)
				}

				Plow.send(evt)
			})
	}

	vm.$onInit = function() {
		vm.loading = true
		_getPost()
	}
}

angular.module("forum").component("forumPostDetail", {
	templateUrl: "/js/mvnApp/app/forum/detail/index.html",
	controller: ForumPostDetailController,
	bindings: {
		user: "=",
		cats: "<",
		showSearchMenu: "="
	}
})

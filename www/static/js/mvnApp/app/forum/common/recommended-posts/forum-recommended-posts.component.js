function ForumRecommendedPostsController(Posts, UrlHelperService) {
	var vm = this,
		req;

	var _getPosts = function() {
		req = {"depth" : 0, "limit" : vm.show, "offset" : 0, "order_by": "popular", "recommended_for_id": vm.post.id };

		if (vm.cat) {
			req.categories = vm.cat.name;
		}
		
		Posts.getPosts().getList(req).then(function(posts) {
			vm.posts = posts;
			vm.loading = false;
		});
	}

	vm.doSlug = function(theTitle) {
		return UrlHelperService.slug(theTitle);
	}

	vm.setLoaders = function(num) {
		return new Array(num);   
	}

	vm.$onInit = function() {
		vm.loading = true;
		_getPosts();
	}
}
angular.module('forum').component('forumRecommendedPosts', {
	templateUrl: '/js/mvnApp/app/forum/common/recommended-posts/_forum-recommended-posts.html',
	controller: ForumRecommendedPostsController,
	bindings: {
		post: '<',
		show: '<'
	}
});
function UserForumRepliesController(Posts) {
	var vm = this,
		postReq,
		pageLimit = 10,
		pageStart = 0,
		totalPosts;


	var getReplies = function(req, onComplete) {
		Posts.getPosts().getList(req).then(function(replies) {
			totalPosts = replies.pagination.total;
			onComplete(replies);
		});
	}

	var setUpReplies = function() {
		postReq = {"depth" : 1, "include_parent": true,  "author_ids" : vm.user.id, "limit" : pageLimit, "offset" : pageStart};
		getReplies(postReq, gotReplies);
	}

	var gotReplies = function(replies) {
		vm.replies = replies;
		vm.loading = false;
	}

	var gotMoreReplies = function(posts) {
		angular.forEach(posts, function (reply) {
			vm.replies.push(reply);
		});
		vm.loadingMore = false;
	}

	vm.loadMore = function() {
		if (totalPosts >= pageStart) {
			vm.loadingMore = true;
			pageStart = pageStart + pageLimit;
			postReq = {"depth" : 1, "include_parent": true,  "author_ids" : vm.user.id, "limit" : pageLimit, "offset" : pageStart };
			getReplies(postReq, gotMoreReplies);
		} else {
			return false;
		}
	}


	vm.$onInit = function() {
		vm.loading = true;
		vm.user = vm.userProfile.user;
		vm.cats = vm.userProfile.cats;
		// if we already have the value of user and cats from our require(d) parent component, go ahead and get the posts. Otherwise, hang tight and grab those values from $onChanges,
		if (vm.user && vm.cats) {
			setUpReplies();
		}
	}

	vm.$onChanges = function(changes) {
		// Because we have to wait for the value of user and cats to be resolved in our parent component (userProfile), we don't want to get the posts till we have both these available.
		var gotUser = changes.user && angular.isUndefined(changes.user.previousValue) && angular.isDefined(changes.user.currentValue),
			gotCats = changes.cats && angular.isUndefined(changes.cats.previousValue) && angular.isDefined(changes.cats.currentValue);

		if ( gotUser && gotCats) {
			setUpReplies();
		}
	} 
}
angular.module('forum').component('userForumReplies', {
	templateUrl: '/js/mvnApp/app/user/profile/replies/index.html',
	controller: UserForumRepliesController,
	require: {
		userProfile: '^userProfile'
	},
	bindings: {
		user: '<',
		cats: '<'
	}
});
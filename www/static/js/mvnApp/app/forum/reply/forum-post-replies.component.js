
function ForumPostRepliesController(Posts) {
	var vm = this,
		req,
		pageLimit = 10,
		pageStart = 0,
		orderBy = 'created_at',
		replyExists;

	var getReplies = function(req, onComplete) {
		Posts.getPosts().getList(req).then(function(replies) {
			onComplete(replies);
		});
	}

	var setUpReplies = function() {
		req = {"parent_ids": vm.post.id, "limit" : pageLimit, "offset" : pageStart, "order_by" : orderBy, "order_direction": "ASC" };
		getReplies(req, gotReplies);
	}

	var gotReplies = function(replies) {
		vm.replies = replies;
		vm.loading = false;
		if (vm.replies.pagination.total <= vm.replies.length) {
			vm.loadedAll = true;
		}
	}

	var gotMoreReplies = function(posts) {

		angular.forEach(posts, function (reply) {
			// if we've just created a reply, we'll have appended that to the list. So we dont' want to re-append it (as a dupe) here. So only add the new reply if it's not already in the list.
			replyExists = _.find(vm.replies, { "id": reply.id } )
			if (!replyExists) {
				vm.replies.push(reply);
			}
		});
		if (vm.replies.pagination.total <= vm.replies.length) {
			vm.loadedAll = true;
		}
		vm.loadingMore = false;
	}

	vm.loadMore = function() {
		if (vm.replies.pagination.total >= pageStart) {
			vm.loadingMore = true;
			pageStart = pageStart + pageLimit;
			req = { "parent_ids": vm.post.id, "limit" : pageLimit, "offset" : pageStart, "order_by": orderBy, "order_direction": "ASC" };
			getReplies(req, gotMoreReplies);
		} else {
			vm.loadedAll = true;
			return false;
		}
	}

	vm.$onInit = function() {
		setUpReplies();
		vm.postUrl = window.location.href
	}
}

angular.module('forum').component('forumPostReplies', {
	templateUrl: '/js/mvnApp/app/forum/reply/_reply-view.html',
	controller: ForumPostRepliesController,
	bindings: {
		user: '<',
		post: '<',
		replies: '='
	}
});
function UserForumQuestionsController(Posts) {
	var vm = this,
		postReq,
		pageLimit = 10,
		pageStart = 0;


	var getPosts = function(req, onComplete) {
		Posts.getPosts().getList(req).then(function(questions) {
			vm.totalPosts = questions.pagination.total;
			onComplete(questions);
		});
	}

	var setUpPosts = function() {
		postReq = { "depth": 0, "author_ids": vm.user.id, "limit": pageLimit, "offset": pageStart };
		getPosts(postReq, gotPosts);
	}

	var gotPosts = function(posts) {
		vm.questions = posts;
		vm.loading = false;
	}

	var gotMorePosts = function(posts) {
		angular.forEach(posts, function(question) {
			vm.questions.push(question);
		});
		vm.loadingMore = false;
	}

	vm.loadingMore = false;
	// Pagination. //TODO: make this into a directive!

	vm.loadMore = function() {
		if (vm.totalPosts >= pageStart) {
			vm.loadingMore = true;
			pageStart = pageStart + pageLimit;
			postReq = { "depth": 0, "author_ids": vm.user.id, "limit": pageLimit, "offset": pageStart };
			getPosts(postReq, gotMorePosts);
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
			setUpPosts();
		}
	}

	vm.$onChanges = function(changes) {
		// Because we have to wait for the value of user and cats to be resolved in our parent component (userProfile), we don't want to get the posts till we have both these available.
		var gotUser = changes.user && angular.isUndefined(changes.user.previousValue) && angular.isDefined(changes.user.currentValue),
			gotCats = changes.cats && angular.isUndefined(changes.cats.previousValue) && angular.isDefined(changes.cats.currentValue);

		if (gotUser && gotCats) {
			setUpPosts();
		}
	}
}
angular.module('forum').component('userForumQuestions', {
	templateUrl: '/js/mvnApp/app/user/profile/questions/index.html',
	controller: UserForumQuestionsController,
	require: {
		userProfile: '^userProfile'
	},
	bindings: {
		user: '<',
		cats: '<'
	}
});
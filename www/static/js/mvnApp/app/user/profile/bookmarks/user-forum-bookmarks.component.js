function UserForumBookmarksController(Bookmarks) {
	var vm = this,
		req,
		totalBookmarks,
		pageLimit = 10,
		pageStart = 0

	var getBookmarks = function(req, onComplete) {
		Bookmarks.getBookmarks()
			.getList({ limit: pageLimit, offset: pageStart })
			.then(function(bookmarks) {
				totalBookmarks = bookmarks.pagination.total
				onComplete(bookmarks)
			})
	}

	var setUpBookmarks = function() {
		req = { limit: pageLimit, offset: pageStart }
		getBookmarks(req, gotBookmarks)
	}

	var gotBookmarks = function(bookmarks) {
		vm.bookmarks = bookmarks
		vm.loading = false
	}

	var gotMoreBookmarks = function(posts) {
		angular.forEach(posts, function(bookmark) {
			vm.bookmarks.push(bookmark)
		})
		vm.loadingMore = false
	}

	vm.loadingMore = false

	vm.loadMore = function() {
		if (totalBookmarks >= pageStart) {
			vm.loadingMore = true
			pageStart = pageStart + pageLimit
			req = { limit: pageLimit, offset: pageStart }
			getBookmarks(req, gotMoreBookmarks)
		} else {
			return false
		}
	}

	vm.$onInit = function() {
		vm.loading = true
		vm.user = vm.userProfile.user
		vm.cats = vm.userProfile.cats
		// if we already have the value of user and cats from our require(d) parent component, go ahead and get the posts. Otherwise, hang tight and grab those values from $onChanges,
		if (vm.user && vm.cats) {
			setUpBookmarks()
		}
	}

	vm.$onChanges = function(changes) {
		// Because we have to wait for the value of user and cats to be resolved in our parent component (userProfile), we don't want to get the posts till we have both these available.
		var gotUser = angular.isUndefined(changes.user.previousValue) && angular.isDefined(changes.user.currentValue),
			gotCats = angular.isUndefined(changes.cats.previousValue) && angular.isDefined(changes.cats.currentValue)

		if (gotUser && gotCats) {
			setUpBookmarks()
		}
	}
}
angular.module("forum").component("userForumBookmarks", {
	templateUrl: "js/mvnApp/app/user/profile/bookmarks/index.html",
	controller: UserForumBookmarksController,
	require: {
		userProfile: "^userProfile"
	},
	bindings: {
		user: "<",
		cats: "<"
	}
})

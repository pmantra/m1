function ForumCommunityController($state, Categories, Posts, Plow, SeoService) {
	let vm = this,
		req,
		evt,
		pageLimit = 30,
		pageStart = 0,
		totalPosts,
		orderBy = "created_at"

	vm.loadingMore = false
	vm.community = {}

	const getPosts = function(req, onComplete) {
		Posts.getPosts()
			.getList(req)
			.then(function(posts) {
				totalPosts = posts.pagination.total
				onComplete(posts)
			})
	}

	const gotMorePosts = function(posts) {
		angular.forEach(posts, function(post) {
			vm.posts.push(post)
		})
		vm.loadingMore = false
	}

	vm.loadMore = function() {
		pageStart = pageStart + pageLimit
		if (totalPosts >= pageStart) {
			vm.loadingMore = true
			req = {
				depth: 0,
				categories: $state.params.community,
				limit: pageLimit,
				offset: pageStart
			}
			getPosts(req, gotMorePosts)
		} else {
			return false
		}
	}

	const getSubcats = function(cat) {
		Categories.getSubCats(cat).then(function(sc) {
			vm.subCats = sc
		})
	}

	vm.$onInit = function() {
		const community = $state.params.community
		const currCat = Categories.currentCat(community, vm.cats) || community
		if (currCat.name) {
			getSubcats(currCat.name)
		}

		evt = {
			event_name: "forum_list",
			user_id: vm.user ? String(vm.user.id) : '',
			community_name: currCat.name ? currCat.name : community
		}

		Plow.send(evt)

		SeoService.setPageTitle({
			title: (currCat.display_name || community.replace(/-/g, " ")) + " – Maven Forum"
		})

		vm.loading = true
		req = {
			depth: 0,
			categories: community,
			limit: pageLimit,
			offset: pageStart,
			order_by: orderBy
		}
		const onComplete = function(posts) {
			vm.posts = posts
			vm.loading = false

			if (!currCat.name) {
				if (posts.length > 0) {
					vm.community = Categories.currentCat(community, posts[0].category_objects)
				} else {
					vm.community = {
						name: community,
						display_name: community.replace(/-/g, " ")
					}
				}
			} else {
				vm.community = currCat
			}
		}
		getPosts(req, onComplete)
	}
}

angular.module("forum").component("forumCommunity", {
	templateUrl: "/js/mvnApp/app/forum/community/index.html",
	controller: ForumCommunityController,
	bindings: {
		user: "<",
		cats: "<",
		showSearchMenu: "="
	}
})

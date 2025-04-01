angular.module("forum").config([
	"$stateProvider",
	"$locationProvider",
	"RestangularProvider",
	function ($stateProvider, $locationProvider, RestangularProvider) {
		$stateProvider
			.state("app.forum", {
				abstract: true,
				bodyClass: "forum page-forum",
				data: {
					noAuth: false,
					enterpriseOnly: true
				},
				template: "<forum></forum>"
			})
			.state("app.forum.search", {
				url: "/forum-search?q",
				template:
					'<forum-search-results user="$ctrl.user" cats="$ctrl.cats" show-search-menu="$ctrl.showSearchMenu" ></forum-search-results>',
				bodyClass: "forum page-forum-search",
				trk_event: "forum-search",
				title: "Search the Maven forum",
				meta: "Get answers to your health and wellness questions from Maven's community of women and practitioners."
			})
			.state("app.forum.landing", {
				url: "/forum",
				template:
					'<forum-landing user="$ctrl.user" cats="$ctrl.cats" show-search-menu="$ctrl.showSearchMenu"></forum-landing>',
				bodyClass: "forum page-app-forum-landing",
				data: {
					noAuth: false,
					enterpriseOnly: true
				},
				trk_event: "forum-landing",
				title: "Welcome to the Maven forum",
				meta: "With Maven, book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health experts – all via your iPhone."
			})
			.state("app.forum.community", {
				url: "/forum/community/:community",
				template:
					'<forum-community user="$ctrl.user" cats="$ctrl.cats" show-search-menu="$ctrl.showSearchMenu" class="forum-community"></forum-community>',
				bodyClass: "page-forum  forum forum-list",
				title: "Maven community",
				meta: "Get the answers you need. Maven's supportive community of healthcare practitioners and women like you are here for you 24/7."
			})
			/* LEGACY - POST DETAIL where commuity param is present. */
			.state("app.forum.community.post-community-detail", {
				url: "^/forum/community/:community/posts/:post_id/:slug",
				template:
					'<forum-post-detail user="$ctrl.user" cats="$ctrl.cats" show-search-menu="$ctrl.showSearchMenu" ></forum-post-detail>',
				params: {
					post_position: {
						value: null
					},
					slug: {
						value: ""
					}
				},
				bodyClass: "page-forum  forum forum-detail",
				title: "Read a post",
				meta: "Get the answers you need. Maven's supportive community of healthcare practitioners and women like you are here for you 24/7."
			})
			/* POST DETAIL */
			.state("app.forum.post-detail", {
				url: "/forum/posts/:post_id/:slug",
				template:
					'<forum-post-detail user="$ctrl.user" cats="$ctrl.cats" show-search-menu="$ctrl.showSearchMenu" ></forum-post-detail>',
				params: {
					post_position: null,
					slug: {
						value: ""
					}
				},
				bodyClass: "page-forum  forum forum-detail",
				title: "Read a post",
				meta: "Get the answers you need. Maven's supportive community of healthcare practitioners and women like you are here for you 24/7."
			})
			/* USER PROFILE */

			.state("app.profile", {
				bodyClass: "page-user-profile",
				url: "/profile",
				data: {
					noAuth: false,
					enterpriseOnly: true
				},
				title: "Your forum profile",
				template: "<user-profile></user-profile>"
			})
			.state("app.profile.bookmarks", {
				url: "/bookmarks",
				title: "Your forum bookmarks",
				template: '<user-forum-bookmarks user="$ctrl.user" cats="$ctrl.cats"></user-forum-bookmarks>',
				bodyClass: "forum page-user-profile body-scroll",
				trk_event: "forum_bookmarks"
			})
			/* MY POSTS LIST */
			.state("app.profile.my_posts", {
				url: "/my-posts",
				title: "My posts",
				template: '<user-forum-questions user="$ctrl.user" cats="$ctrl.cats"></user-forum-questions>',
				data: {
					noAuth: false
				},
				bodyClass: "forum page-user-profile body-scroll",
				trk_event: "forum_my_posts"
			})
			/* MY REPLIES LIST */
			.state("app.profile.my_replies", {
				url: "/my-replies",
				title: "My replies",
				template: '<user-forum-replies user="$ctrl.user" cats="$ctrl.cats"></user-forum-replies>',
				data: {
					noAuth: false
				},
				bodyClass: "forum page-user-profile body-scroll",
				trk_event: "forum_my_replies"
			})
			/* CREATE POST */
			.state("app.forum.create-post", {
				url: "/forum/post/create?community&ama",
				title: "Write a new post",
				template:
					'<forum-create-post user="$ctrl.user" cats="$ctrl.cats" sub-cats="$ctrl.subCats" show-search-menu="$ctrl.showSearchMenu" ></forum-create-post>',
				trk_event: "forum_new_post",
				bodyClass: "page-forum forum forum-create",
				data: {
					noAuth: false
				}
			})
	}
])

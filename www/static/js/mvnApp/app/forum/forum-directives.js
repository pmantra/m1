/* Forum Directives */

angular.module("forum").directive("postListView", [
	"$state",
	"Categories",
	"ngNotify",
	"ModalService",
	"UrlHelperService",
	function($state, Categories, ngNotify, ModalService, UrlHelperService) {
		return {
			scope: {
				post: "=",
				cats: "=",
				user: "=",
				incommunity: "@",
				showSearchMenu: "="
			},
			restrict: "E",
			link: function(scope, elem, attrs) {
				var titleSlug = UrlHelperService.slug(scope.post.title),
					mainCategory = Categories.mainCat(scope.cats, scope.post.categories).name,
					totalReplies = scope.post.reply_counts.practitioners + scope.post.reply_counts.members

				if (totalReplies === 1) {
					scope.btnText = "View 1 reply"
				} else if (totalReplies >= 2) {
					scope.btnText = `View ${totalReplies} replies`
				} else {
					scope.btnText = "Be the first to reply"
				}
				// scope.btnText = totalReplies >= 1 ? `View ${totalReplies} replies` : "Be the first to reply"

				scope.openPost = function() {
					// if we want to open the post as a child of a community (with corresponding url)...
					/*if (scope.incommunity) {
						// we update the url... but dont actually transition to this state. We sneakily open the post in a modal instead so we can persist the infinite scroll posts and position.
						$state.transitionTo(
							"app.forum.community.post-community-detail",
							{
								post_id: scope.post.id,
								slug: titleSlug,
								community: mainCategory,
								nonext: true,
								m: true
							},
							{ reloadOnSearch: false }
						);
						ModalService.openPostDetail(scope.post, scope.cats);
					} else {*/
					$state.go(
						"app.forum.community.post-community-detail",
						{
							post_id: scope.post.id,
							slug: titleSlug,
							community: mainCategory,
							nonext: true,
							m: true
						},
						{}
					)
					//}
				}
			},
			replace: true,
			templateUrl: "/js/mvnApp/app/forum/community/_post-list-view.html"
		}
	}
])

angular.module("forum").directive("myRepliesListView", function() {
	return {
		scope: {
			post: "<",
			user: "<"
		},
		restrict: "E",
		templateUrl: "/js/mvnApp/app/user/profile/replies/_my-replies-list-view.html"
	}
})

angular.module("forum").directive("createReply", function() {
	return {
		restrict: "E",
		templateUrl: "/js/mvnApp/app/forum/reply/_create-reply.html"
	}
})

/* Avatars */

angular.module("forum").directive("postAuthor", [
	"$rootScope",
	"$state",
	"ModalService",
	function($rootScope, $state, ModalService) {
		return {
			restrict: "E",
			scope: {
				author: "=",
				datetime: "=",
				viewPrac: "&"
			},
			link: function(scope) {
				var evt

				scope.goBookPrac = function(pracId) {
					if ($rootScope.isAuthenticated) {
						$state.go("app.practitioner-profile", { practitioner_id: pracId })
					} else {
						var onComplete = function() {
							$state.go("app.practitioner-profile", {
								practitioner_id: pracId
							})
							evt = {
								event_name: "forum_view_prac_profile_from_post",
								user_id: String($rootScope.user.id)
							}

							scope.$emit("trk", evt)
						}

						ModalService.loginRegModal(onComplete)
					}
				}

				if (!scope.author) {
					scope.name = "Anonymous"
				} else {
					if (scope.author.profiles.practitioner) {
						scope.authorProfession = scope.author.profiles.practitioner.verticals[0]
					}
					// if practitoner, show first and last name, otherwise username.
					scope.name = scope.author.profiles.practitioner
						? scope.author.first_name + " " + scope.author.last_name
						: scope.author.username
				}
			},
			templateUrl: "/js/mvnApp/app/forum/shared/_post-author.html"
		}
	}
])

/* Send message to practitioner button */
angular.module("forum").directive("sendMessage", [
	"$rootScope",
	"Messages",
	"ModalService",
	function($rootScope, Messages, ModalService) {
		return {
			restrict: "E",
			scope: {
				author: "="
			},
			link: function(scope, element, attrs) {
				var evt

				var sendMessage = function(pracID, userID) {
					Messages.newChannel(pracID, userID).then(function(c) {
						var newChannel = c
						var onComplete = function() {
							ModalService.messageSent()
							evt = {
								event_name: "web_forum_send_prac_message_complete",
								user_id: String(userID),
								practitioner_id: String(pracID)
							}

							scope.$emit("trk", evt)
						}
						ModalService.newPractitionerMessage(newChannel, onComplete)
					})
				}

				scope.goMessagePrac = function(pracID) {
					let pracType = scope.author.profiles.practitioner.care_team_type === "CARE_COORDINATOR" ? "cx" : "prac"

					if ($rootScope.isAuthenticated) {
						evt = {
							event_name: `web_click_forum_send_${pracType}_message`,
							user_id: String($rootScope.user.id),
							practitioner_id: String(pracID)
						}

						scope.$emit("trk", evt)

						sendMessage(pracID, $rootScope.user.id)
					} else {
						evt = {
							event_name: `web_unauth_click_forum_send_${pracType}_message`,
							user_id: '',
							practitioner_id: String(pracID)
						}

						scope.$emit("trk", evt)

						var onComplete = function(newU) {
							sendMessage(pracID, newU.id)
						}

						ModalService.loginRegModal(onComplete)
					}
				}

				scope.cta = attrs.cta
				scope.btnCta = attrs.btnCta || "Send a message"
				scope.btnType = attrs.btnType || "btn-cta"
			},
			templateUrl: "/js/mvnApp/app/forum/shared/_send-message.html"
		}
	}
])

/* Toggle following a post */
angular.module("forum").directive("mvnBookmarkPost", [
	"$rootScope",
	"Posts",
	"ngNotify",
	"ModalService",
	"ngDialog",
	"$timeout",
	function($rootScope, Posts, ngNotify, ModalService, ngDialog, $timeout) {
		return {
			scope: {
				post: "=",
				user: "=",
				updatePostStatus: "&"
			},
			restrict: "E",
			link: function(scope, element, attrs) {
				var doBookmark = function() {
					if (scope.post.has_bookmarked) {
						Posts.getPost(scope.post.id)
							.one("bookmarks")
							.remove()
							.then(
								function(bookmark) {
									ngNotify.set("Removed bookmark", "success")
									scope.post.has_bookmarked = false
									scope.post.bookmarks_count--
								},
								function(e) {
									ngNotify.set(e.data.message, "error")
								}
							)
					} else {
						Posts.getPost(scope.post.id)
							.one("bookmarks")
							.post()
							.then(
								function(bookmark) {
									ngNotify.set("Bookmarked!", "success")
									scope.post.has_bookmarked = true
									scope.post.bookmarks_count++
								},
								function(e) {
									ngNotify.set(e.data.message, "error")
								}
							)
					}
				}

				// Throttling function to wrap around doBookmark
				var throttledDoBookmark = function() {
					if (!throttledDoBookmark.timer) {
						throttledDoBookmark.timer = $timeout(function() {
							doBookmark();
							throttledDoBookmark.timer = null;
						}, 1000);
					}
				};
				

				scope.toggleBookmarked = function() {
					if (scope.user) {
						throttledDoBookmark()
					} else {
						var onComplete = function(user, modalId) {
							scope.user = user
							ngDialog.close(modalId)
							throttledDoBookmark()
						}

						ModalService.loginRegModal(onComplete)
					}
				}
			},
			template:
				'<a class="icon-bookmark" href="" ng-class="{ bookmarked: post.has_bookmarked }" ng-click="toggleBookmarked()">' +
				'<svg width="20" height="17" viewBox="0 0 22 25" xmlns="http://www.w3.org/2000/svg"><title>Bookmark post</title><path stroke="#00856f" stroke-width="1.2" d="M20.777 23.808l-9.87-6.842L1 23.808V1h19.777z" fill="none" fill-rule="evenodd" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
				'<span ng-if="post.has_bookmarked">Bookmarked</span>' +
				'<span ng-if="!post.has_bookmarked">Bookmark</span>' +
				"</a>"
		}
	}
])

/* Toggle Liking a reply */
angular.module("forum").directive("mvnReplyVotes", [
	"$rootScope",
	"Posts",
	"Plow",
	"ngNotify",
	"ModalService",
	function($rootScope, Posts, Plow, ngNotify, ModalService) {
		return {
			scope: {
				reply: "=",
				user: "="
			},
			restrict: "E",
			link: function(scope, element, attrs) {
				var doLike = function() {
					if (!scope.reply.has_voted) {
						Posts.voteOnPost(scope.reply.id, "up").then(
							function() {
								var evt = {
									event_name: "forum_upvote_post",
									user_id: String(scope.user.id)
								}
								var trkData = {
									post_id: scope.reply.id
								}

								Plow.send(evt, trkData)

								scope.reply.net_votes++
								scope.reply.has_voted = true
							},
							function(e) {
								ngNotify.set(e.data.message, "error")
							}
						)
					} else {
						Posts.removeVote(scope.reply.id).then(
							function() {
								var evt = {
									event_name: "forum_remove_upvote",
									user_id: String(scope.user.id)
								}
								var trkData = {
									post_id: String(scope.post_id)
								}

								Plow.send(evt, trkData)

								scope.reply.net_votes--
								scope.reply.has_voted = false
							},
							function(e) {
								ngNotify.set(e.data.message, "error")
							}
						)
					}
				}

				scope.toggleLiked = function() {
					if ($rootScope.isAuthenticated) {
						doLike()
					} else {
						var onComplete = function() {
							doLike()
						}
						ModalService.loginRegModal(onComplete)
					}
				}
			},
			template:
				'<p class="votes-header">Was this helpful?</p>' +
				'<span class="icon-was-helpful" ng-click="toggleLiked()">' +
				'<svg width="22" height="22" viewBox="0 0 22 22" xmlns="http://www.w3.org/2000/svg"><title>yes</title><g fill="none" fill-rule="evenodd"><path d="M20.357 10.928c0 5.208-4.22 9.43-9.43 9.43a9.428 9.428 0 0 1-9.427-9.43 9.43 9.43 0 0 1 18.857 0z" stroke="#00856f" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M14.99 12.71a4.808 4.808 0 0 1-4.015 2.156 4.81 4.81 0 0 1-4.108-2.305" stroke="#111111" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 8a1 1 0 1 1-2 0 1 1 0 0 1 2 0M15 8a1 1 0 1 1-2 0 1 1 0 0 1 2 0" fill="#111111"/></g></svg>' +
				"<h5>Yes</h5>" +
				'<span class="vote-count" ng-class="{ voted: reply.has_voted }"> {{ reply.net_votes }}</span>' +
				"</span> "
		}
	}
])

/* Absolute postition with fixed child */
angular.module("forum").directive("parentWidth", function($window) {
	return function(scope, element, attr) {
		var w = angular.element($window)

		var onResize = function() {
			element.css({
				width: element.parent()[0].offsetWidth
			})
		}

		// Get parent elmenets width and subtract fixed width
		element.css({
			width: element.parent()[0].offsetWidth
		})

		w.on("resize", onResize)

		scope.$on("$destroy", function() {
			// clean the resize event listener up manually because it won't get automatically cleaned up by the directive as the scrollContainer is outside of the directive in the DOM
			w.off("resize", onResize)
		})
	}
})

angular.module("forum").directive("communityHeadline", [
	"Posts",
	"Categories",
	function(Posts, Categories) {
		return {
			restrict: "E",
			scope: {
				community: "=",
				post: "=",
				user: "=",
				cats: "="
			},
			controller: function($scope, UrlHelperService) {
				$scope.slug = function(str) {
					return UrlHelperService.slug(str)
				}
			},
			link: function(scope, element, attrs) {
				scope.postMainCat = Categories.mainCat(scope.cats, scope.post.categories)
			},
			templateUrl: "/js/mvnApp/app/forum/forum-landing/_post-forum-landing.html"
		}
	}
])

/* Inline loader */
angular.module("forum").directive("inlineLoader", [
	function() {
		return {
			scope: {
				label: "@"
			},
			restrict: "E",
			replace: true,
			template:
				'<div class="loader-inline">' +
				'<div class="loader-inline-content">' +
				'<div class="h5"><span class="loader-spin">' +
				'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid" class="uil-ripple"><rect x="0" y="0" width="100" height="100" fill="none" class="bk"></rect><g> <animate attributeName="opacity" dur="2s" repeatCount="indefinite" begin="0s" keyTimes="0;0.33;1" values="1;1;0"></animate><circle cx="50" cy="50" r="40" stroke="#111111" fill="none" stroke-width="6" stroke-linecap="round"><animate attributeName="r" dur="2s" repeatCount="indefinite" begin="0s" keyTimes="0;0.33;1" values="0;22;44"></animate></circle></g><g><animate attributeName="opacity" dur="2s" repeatCount="indefinite" begin="1s" keyTimes="0;0.33;1" values="1;1;0"></animate><circle cx="50" cy="50" r="40" stroke="#111111" fill="none" stroke-width="6" stroke-linecap="round"><animate attributeName="r" dur="2s" repeatCount="indefinite" begin="1s" keyTimes="0;0.33;1" values="0;22;44"></animate></circle></g></svg>' +
				"</span> {{ label }}</div>" +
				"</div>" +
				"</div>"
		}
	}
])

/* Infinite Scroll */
angular.module("forum").directive("mvnInfScroll", [
	function() {
		return {
			restrict: "EA",
			scope: {
				scrollContainer: "=",
				scrollAction: "&",
				isLoading: "="
			},
			link: function(scope, element, attrs) {
				var theContainer = document.getElementById(attrs.scrollContainer),
					scrollContainer = angular.element(theContainer),
					scrollContent = element[0]

				var onScroll = function() {
					if (this.scrollTop + this.offsetHeight >= scrollContent.scrollHeight - 100 && !scope.isLoading) {
						scope.$apply(scope.scrollAction)
					}
				}

				var debouncedScroll = _.debounce(onScroll, 300)

				scrollContainer.on("scroll", debouncedScroll)

				scope.$on("$destroy", function() {
					// clean the scroll event listener up manually because it won't get automatically cleaned up by the directive as the scrollContainer is outside of the directive in the DOM
					scrollContainer.off("scroll", onScroll)
				})
			}
		}
	}
])

/* User select avatar color*/
angular.module("forum").directive("userSelectAvatarColor", [
	"$rootScope",
	"ngNotify",
	"Users",
	"observeOnScope",
	function($rootScope, ngNotify, Users, observeOnScope) {
		return {
			scope: {
				user: "=",
				onComplete: "&"
			},
			restrict: "E",
			link: function(scope, element, attrs) {
				if (scope.user.username) {
					var fLetter = scope.user.username.slice(0, 1)

					if (fLetter.match(/[a-zA-Z]/i)) {
						scope.avatarLetter = fLetter
					} else {
						scope.userAvatar = "#"
					}
				} else {
					scope.avatarLetter = "M"
				}

				scope.colors = ["111111", "00413e", "ffcac1", "8ead9f", "b97965", "f5d1ba"]

				scope.selectedColor = scope.user.profiles.member.color_hex ? scope.user.profiles.member.color_hex : null

				var _updateUser = function(newCol) {
					scope.updatingColor = true
					scope.user.profiles.member.color_hex = newCol
					Users.updateUserProfile(scope.user.id, scope.user.profiles.member).then(function(u) {
						Users.getWithProfile(true).then(function(usr) {
							scope.user = usr
							$rootScope.$broadcast("updateUser", usr)
							scope.updatingColor = false
							scope.hasClicked = false
							ngNotify.set("Saved your avatar color!", "success")
						}, handleError)
					}, handleError)
				}

				var handleError = function(e) {
					scope.hasClicked = false
					ngNotify.set(
						"Sorry there seems to have been a problem! Try again or contact support@mavenclinic.com if the issue persists.",
						"error"
					)
				}

				scope.selectColor = function(col) {
					if (col !== scope.selectedColor) {
						scope.hasClicked = true
					}
					scope.selectedColor = col
				}

				observeOnScope(scope, "selectedColor")
					.safeApply(scope, function(data) {
						if (data.newValue) {
							scope.selectedColor = data.newValue
						}
					})
					.debounce(1000)
					.subscribe(function(change) {
						if (change.newValue && change.newValue !== scope.user.profiles.member.color_hex) {
							_updateUser(change.newValue)
						}
					})
			},
			template:
				'<ul class="clear clearfix">' +
				'<li ng-repeat="color in colors" style="background: #{{ color }};" ng-class="{ saving : hasClicked, selected: color == selectedColor }" ng-click="selectColor(color)">' +
				'<span class="avatar-letter">{{ ::avatarLetter }}</span>' +
				'<span ng-if="(color == selectedColor) && !updatingColor && !hasClicked" class="is-selected"><svg width="19" height="13" viewBox="0 0 19 13" xmlns="http://www.w3.org/2000/svg"><title>Selected</title><path d="M1 6.525L6.63 12 17.89 1.05" stroke-width="2" stroke="#FFF" fill="none" fill-rule="evenodd" stroke-linecap="round" stroke-linejoin="round"/></svg></span>' +
				'<span class="loader-spin">' +
				'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid" class="uil-ripple"><rect x="0" y="0" width="100" height="100" fill="none" class="bk"></rect><g> <animate attributeName="opacity" dur="2s" repeatCount="indefinite" begin="0s" keyTimes="0;0.33;1" values="1;1;0"></animate><circle cx="50" cy="50" r="40" stroke="#ffffff" fill="none" stroke-width="6" stroke-linecap="round"><animate attributeName="r" dur="2s" repeatCount="indefinite" begin="0s" keyTimes="0;0.33;1" values="0;22;44"></animate></circle></g><g><animate attributeName="opacity" dur="2s" repeatCount="indefinite" begin="1s" keyTimes="0;0.33;1" values="1;1;0"></animate><circle cx="50" cy="50" r="40" stroke="#fffcfb" fill="none" stroke-width="6" stroke-linecap="round"><animate attributeName="r" dur="2s" repeatCount="indefinite" begin="1s" keyTimes="0;0.33;1" values="0;22;44"></animate></circle></g></svg>' +
				"</span>" +
				"</li>" +
				"</ul>" +
				'<p ng-if="updatingColor" class="center">Saving...</p>'
		}
	}
])

/* Write a Post CTA */
angular.module("forum").directive("writePost", function() {
	return {
		restrict: "E",
		template:
			'<div class="center forum-post-cta">' +
			'<div class="cta-container">' +
			"<span>Have a question of your own?</span>" +
			'<a class="btn btn-cta" ui-sref="app.forum.create-post">Write a post</a>' +
			"</div>" +
			"</div>"
	}
})

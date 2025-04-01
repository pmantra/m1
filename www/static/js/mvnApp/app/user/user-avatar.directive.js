angular.module("app").directive("userAvatar", [
	function () {
		return {
			restrict: "E",
			scope: {
				user: "=",
				show: "@"
			},
			link: function (scope) {
				if (scope.user) {
					if (scope.user.image_id) {
						scope.hasImg = true
						scope.avatarClass = scope.user.profiles.practitioner ? "has-photo prac-photo" : "has-photo"
					} else {
						// if has no photo but is a practitioner, show the maven logo
						if (scope.user.profiles.practitioner) {
							scope.hasIcon = true
							scope.avatarClass = "avatar-icon noimg practitioner"
						} else {
							scope.hasLetter = true
							scope.avatarBgCol =
								scope.user.profiles.member && scope.user.profiles.member.color_hex
									? "#" + scope.user.profiles.member.color_hex
									: ""

							const nameToUse = scope.show && scope.show === "username" ? "username" : "first_name"
							const fLetter = scope.user[nameToUse].slice(0, 1)
							const lLetter = scope.user.last_name.slice(0, 1)

							if (fLetter.match(/[a-zA-Z]/i) && lLetter.match(/[a-zA-Z]/i)) {
								scope.avatarLetter = fLetter
							} else {
								scope.avatarLetter = "#"
							}
						}
					}
				} else {
					scope.noAvatar = true
				}
			},
			template: `
				<span ng-if="hasImg" class="avatar-wrap" ng-class="avatarClass">
					<img ng-src="{{user.image_url}}" class="avatar" width="48" height="48" alt="" />
				</span>

				<span ng-if="hasIcon" class="avatar-wrap" ng-class="avatarClass">
					<svg width="50" height="28" aria-hidden="true" viewBox="0 8 50 28" xmlns="http://www.w3.org/2000/svg"><title>Maven icon</title><path d="M47.83 23.35c-3.68 0-6.88-2.1-8.5-5.2-.45 1.4-1.07 2.72-1.85 3.92 2.44 3.06 6.18 5.02 10.35 5.02 1.02 0 1.84-.85 1.84-1.88 0-1.03-.82-1.87-1.84-1.87v.01zm-9.1-13.08c.16-.47.36-.92.6-1.36 1.62-3.08 4.82-5.18 8.5-5.18 1.02 0 1.84-.84 1.84-1.87C49.67.84 48.85 0 47.83 0c-4.17 0-7.9 1.96-10.35 5.02-.2.26-.4.53-.6.8-.2.28-.37.57-.54.87-1.17 2-1.84 4.35-1.84 6.84 0 1.15-.2 2.24-.55 3.26-.17.47-.37.93-.6 1.36-1.62 3.1-4.83 5.2-8.5 5.2-3.7 0-6.9-2.1-8.53-5.2-.43 1.4-1.06 2.7-1.84 3.9 2.45 3.07 6.18 5.03 10.36 5.03 4.17 0 7.9-1.97 10.36-5.03.2-.26.4-.53.58-.8.2-.28.38-.58.56-.87 1.16-2.02 1.83-4.36 1.83-6.86 0-1.14.2-2.24.56-3.26v.01zM1.83 3.74c3.7 0 6.9 2.1 8.53 5.18.43-1.4 1.05-2.7 1.84-3.9C9.75 1.96 6.02 0 1.84 0 .82 0 0 .84 0 1.87 0 2.9.82 3.74 1.84 3.74h-.01zm13.91 6.54c.15-.47.35-.92.58-1.36 1.63-3.08 4.84-5.18 8.52-5.18 3.68 0 6.9 2.1 8.5 5.18.45-1.4 1.07-2.7 1.86-3.9C32.75 1.96 29 0 24.84 0c-4.18 0-7.9 1.96-10.36 5.02-.2.26-.4.53-.6.8-.18.28-.37.57-.54.87-1.17 2-1.84 4.35-1.84 6.84 0 1.15-.2 2.24-.55 3.26-.17.47-.36.93-.6 1.36-1.62 3.1-4.83 5.2-8.5 5.2C.8 23.35 0 24.18 0 25.2c0 1.03.82 1.87 1.84 1.87 4.18 0 7.9-1.97 10.36-5.03.2-.26.4-.53.6-.8.18-.28.37-.58.54-.87 1.17-2.02 1.84-4.36 1.84-6.86 0-1.14.2-2.24.55-3.26l.01.03z" fill="#ffffff" fill-rule="evenodd"/></svg></span>
				</span>

				<span ng-if="hasLetter" class="avatar-wrap">
					<span class="avatar-icon noimg"  ng-style="{'background-color': avatarBgCol}">
						{{ avatarLetter }}
					</span>
				</span>

				<span ng-if="noAvatar" class="avatar-wrap">
					<span class="avatar-icon anon" tabindex="-1" aria-hidden="true">?</span>
				</span>
						`
		}
	}
])

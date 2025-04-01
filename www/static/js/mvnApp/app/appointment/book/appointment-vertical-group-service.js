angular.module("appointment").factory("VerticalGroupService", [
	"v2Api",
	function(v2Api) {
		var verticalGroupService = {}

		verticalGroupService.get = function() {
			return v2Api
				.one("/_/vertical_groupings")
				.get()
				.then(
					function(resp) {
						return resp
					},
					function(err) {
						return err
					}
				)
		}

		verticalGroupService.getVerticals = function(group, version) {
			return v2Api
				.one("/_/vertical_groupings")
				.get({ version: version })
				.then(
					function(resp) {
						var verticals = [],
							groupings

						/* get the requiredvertical group from the result of all of them */
						groupings = _.find(resp, function(item) {
							return item.name == group
						})

						/* get the vertical ids we need to filter the practitioner list... */

						// if we have a matching vertical group, add the vertical ids to our list of verticals
						if (groupings) {
							for (var i = groupings.verticals.length - 1; i >= 0; i--) {
								verticals.push(groupings.verticals[i].id)
							}

							/* make them into a comma separated string */
							return verticals.toString()
						} else {
							// if we have  no vertical groups matching that name, return null so we dont filter by vertical ids... instead of breaking all the things... ;)
							return null
						}
					},
					function(err) {
						return err
					}
				)
		}

		return verticalGroupService
	}
])

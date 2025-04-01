/**
 * @ngdoc function
 * @name Forum Categories
 * @description
 * # Categories
 * Maven login controller
 */
angular.module("forum").factory("Categories", [
	"$q",
	"Restangular",
	function($q, Restangular) {
		var service = {},
			globalCats,
			subCats

		service.getCats = function() {
			if (!globalCats) {
				return Restangular.all("categories")
					.getList({ client_name: "Web" }) // make dynamic  sub_
					.then(
						function(c) {
							//ask-jackie
							//globalCats = _.filter(c.plain(), function(o) { return o.name !== 'ask-jackie'; });
							globalCats = c.plain()
							// add a "special" property on FE for now for promo category
							for (var i = globalCats.length - 1; i >= 0; i--) {
								if (globalCats[i].name === "ask-jackie" || globalCats[i].name === "harassment-ama") {
									globalCats[i].special = true
									globalCats[i].archived = true
								}
							}
							return globalCats
						},
						function(e) {
							return false
						}
					)
			} else {
				return $q.resolve(globalCats)
			}
		}

		service.getSubCats = function(cat) {
			//TODO: combine this with the getCats() function - subcategories will be a nested array for each category in the returned array
			return Restangular.all("categories")
				.getList({ client_name: `sub_` + cat })
				.then(function(sc) {
					subCats = sc.plain()
					return subCats
				})
		}

		//get category object where we have a single category item
		service.currentCat = function(cat, cats) {
			//TODO: better way of finding current category..
			var theCat
			for (var i = cats.length - 1; i >= 0; i--) {
				if (cats[i].name === cat) {
					theCat = cats[i]
					return theCat
				}
			}
		}

		// Get post's category where there may be multiple - only use the one in our global categories list
		service.mainCat = function(cats, postcats) {
			var cat
			// loop through post's categories
			for (var p = postcats.length - 1; p >= 0; p--) {
				//and check for a match in the main categories object...
				for (var i = cats.length - 1; i >= 0; i--) {
					if (cats[i].name === postcats[p]) {
						cat = cats[i]
						return cat
					}
				}
			}
		}

		return service
	}
])

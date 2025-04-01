// Karma configuration
// Generated on Thu Nov 16 2017 14:27:45 GMT-0500 (EST)

module.exports = function(config) {
  config.set({

    // base path that will be used to resolve all patterns (eg. files, exclude)
    basePath: '../',


    // frameworks to use
    // available frameworks: https://npmjs.org/browse/keyword/karma-adapter
    frameworks: ['jasmine'],


    // list of files / patterns to load in the browser
    files: [
      'www/static/js/vendor/**/*.js',
      {pattern: 'www/node_modules/angular-mocks/angular-mocks.js', included: true, served: true, watched: false},
      'www/static/js/*.js',
      //{pattern: 'www/static/index.html', included: false, served: true, watched: true},
      'www/static/js/mvnApp/**/*.test.js' // load tests
    ],

    // list of files to exclude
    exclude: [
    ],

    proxies: {
      // Having these not commented out prevents the warning re: web-server when running karma in debug mode.
     // '/js/': 'https://www.mvnctl.net:8888/js/', //TODO - is this gonna break all the shit on gitlab???
      '/api/v1/': '/base/api/v1/' 
    },

    proxyValidateSSL: false,
    // preprocess matching files before serving them to the browser
    // available preprocessors: https://npmjs.org/browse/keyword/karma-preprocessor
    preprocessors: {
    },


    // test results reporter to use
    // possible values: 'dots', 'progress'
    // available reporters: https://npmjs.org/browse/keyword/karma-reporter
    reporters: ['progress'],


    // web server port
    port: 9876,


    // enable / disable colors in the output (reporters and logs)
    colors: true,


    // level of logging
    // possible values: config.LOG_DISABLE || config.LOG_ERROR || config.LOG_WARN || config.LOG_INFO || config.LOG_DEBUG
    logLevel: config.LOG_DEBUG,

    // up default timeout levels
    browserNoActivityTimeout: 100000,
    browserDisconnectTimeout: 60000,
    captureTimeout: 60000,
    browserDisconnectTolerance: 3,

    // custom config/debug html templates - including base href tag
    customContextFile: 'www/static/js/mvnApp/test/context.html',
    customDebugFile:   'www/static/js/mvnApp/test/debug.html',
    
    // enable / disable watching file and executing tests whenever any file changes
    autoWatch: true,


    // start these browsers
    // available browser launchers: https://npmjs.org/browse/keyword/karma-launcher
    browsers: ['PhantomJS'],


    // Continuous Integration mode
    // if true, Karma captures browsers, runs the tests and exits
    singleRun: false,

    // Concurrency level
    // how many browser should be started simultaneous
    concurrency: Infinity
  })
}

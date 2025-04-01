const webpack = require('webpack');
const path = require('path');
const sass = require('sass');

module.exports = {
  resolve: {
    extensions: ['.js', '.jsx'],
  },
  entry: ['babel-polyfill', './index.js'],
  output: {
    libraryTarget: 'var',
    library: 'AdminTool',
    path: path.resolve(__dirname, '../static/js-dev'),
    filename: 'app-dev.js',
  },
  watch: true,
  watchOptions: {
    ignored: /node_modules/,
  },
  cache: false,
  module: {
    rules: [
      {
        test: /\.(js|jsx)$/,
        loader: 'babel-loader',
        include: __dirname,
      },
      {
        test: /\.json$/,
        loader: 'json-loader',
      },
      {
        test: /\.css$/,
        loader: 'style-loader!css-loader',
      },
      {
        test: /\.scss$/,
        use: [
          'style-loader',
          'css-loader',
          {
            loader: 'sass-loader',
            options: {
              implementation: sass,
            },
          },
        ],
      },
      {
        test: /\.(ttf|otf|eot|svg)(\?v=[0-9]\.[0-9]\.[0-9])?|(jpg|gif)$/,
        loader: 'file-loader',
      },
      {
        test: /\.woff($|\?)|\.woff2($|\?)/,
        loader: 'url-loader',
      },
    ],
  },
  plugins: [
    new webpack.ProvidePlugin({
      $: 'jquery',
      jQuery: 'jquery',
    }),
  ],
};

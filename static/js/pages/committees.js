'use strict';

/* global document */

var $ = require('jquery');

var tables = require('../modules/tables');
var helpers = require('../modules/helpers');

var FilterPanel = require('fec-style/js/filter-panel').FilterPanel;
var filterTags = require('fec-style/js/filter-tags');

var committeesTemplate = require('../../templates/committees.hbs');

var columns = [
  {
    data: 'name',
    className: 'all',
    width: '280px',
    render: function(data, type, row, meta) {
      return tables.buildEntityLink(
        data,
        helpers.buildAppUrl(
          ['committee', row.committee_id],
          tables.getCycle(row.cycles, meta)
        ),
        'committee'
      );
    }
  },
  {data: 'treasurer_name', className: 'min-desktop hide-panel'},
  {data: 'state', className: 'min-desktop hide-panel', width: '60px'},
  {data: 'party_full', className: 'min-desktop hide-panel'},
  tables.dateColumn({data: 'first_file_date', className: 'min-tablet hide-panel'}),
  {data: 'committee_type_full', className: 'min-tablet hide-panel'},
  {data: 'designation_full', className: 'min-tablet hide-panel'},
  {data: 'organization_type_full', className: 'min-desktop hide-panel'},
  {
    className: 'all u-no-padding',
    width: '20px',
    orderable: false,
    render: function(data, type, row, meta) {
      return tables.MODAL_TRIGGER_HTML;
    }
  }
];

$(document).ready(function() {
  var $table = $('#results');
  var $widgets = $('.js-data-widgets');
  var $tagList = new filterTags.TagList({title: 'All records'}).$body;
  var filterPanel = new FilterPanel();
  new tables.DataTable($table, {
    title: 'Committee',
    panel: filterPanel,
    path: ['committees'],
    columns: columns,
    useFilters: true,
    useExport: true,
    order: [[4, 'desc']],
    rowCallback: tables.modalRenderRow,
    callbacks: {
      afterRender: tables.modalRenderFactory(committeesTemplate)
    }
  });
  $widgets.prepend($tagList);
});

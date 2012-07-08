//----------------------------------------------------------------------------
//  Copyright (C) 2008-2011  The IPython Development Team
//
//  Distributed under the terms of the BSD License.  The full license is in
//  the file COPYING, distributed as part of this software.
//----------------------------------------------------------------------------

//============================================================================
// NotebookList
//============================================================================

var IPython = (function (IPython) {

    var NotebookList = function (selector) {
        this.selector = selector;
        if (this.selector !== undefined) {
            this.element = $(selector);
            this.style();
            this.bind_events();
        }
    };

    NotebookList.prototype.style = function () {
        $('#notebook_toolbar').addClass('list_toolbar');
        $('#drag_info').addClass('toolbar_info');
        $('#notebook_buttons').addClass('toolbar_buttons');
        $('#refresh_notebook_list').button({
            icons : {primary: 'ui-icon-arrowrefresh-1-s'},
            text : false
        });
    };


    NotebookList.prototype.bind_events = function () {
        if (IPython.read_only){
            return;
        }
        var that = this;
        $('#refresh_notebook_list').click(function () {
            that.load_list();
        });
        this.element.bind('dragover', function () {
            return false;
        });
        this.element.bind('drop', function(event){
            that.handelFilesUpload(event,'drop');
            return false;
        });
    };

    NotebookList.prototype.handelFilesUpload =  function(event, dropOrForm) {
        var that = this;
        var files;
        if(dropOrForm =='drop'){
            files = event.originalEvent.dataTransfer.files;
        } else 
        {
            files = event.originalEvent.target.files
        }
        for (var i = 0, f; f = files[i]; i++) {
            var reader = new FileReader();
            reader.readAsText(f);
            var fname = f.name.split('.'); 
            var nbname = fname.slice(0,-1).join('.');
            var nbformat = fname.slice(-1)[0];
            if (nbformat === 'ipynb') {nbformat = 'json';};
            if (nbformat === 'py' || nbformat === 'json') {
                var item = that.new_notebook_item(0);
                that.add_name_input(nbname, item);
                item.data('nbformat', nbformat);
                // Store the notebook item in the reader so we can use it later
                // to know which item it belongs to.
                $(reader).data('item', item);
                reader.onload = function (event) {
                    var nbitem = $(event.target).data('item');
                    that.add_notebook_data(event.target.result, nbitem);
                    that.add_upload_button(nbitem);
                };
            };
        }
        return false;
        };

    NotebookList.prototype.clear_list = function () {
        this.element.children('.list_item').remove();
    }


    NotebookList.prototype.load_list = function () {
        var settings = {
            processData : false,
            cache : false,
            type : "GET",
            dataType : "json",
            success : $.proxy(this.list_loaded, this)
        };
        var url = $('body').data('baseProjectUrl') + 'notebooks';
        $.ajax(url, settings);
    };


    NotebookList.prototype.project_notebook_list_load = function (project, data) {
        pdiv = $('.project-notebook-list[project="'+project+'"]')[0];
        if(!pdiv){
            pdiv = this.new_project_div(project);
        }
        var len = data.length;

        pdiv = $(pdiv)    
        pdiv.children('.list_item').remove();

        for (var i=0; i<len; i++) {
            var notebook_id = data[i].notebook_id;
            var nbname = data[i].name;
            var kernel = data[i].kernel_id;
            var item = this.new_notebook_item(i, pdiv);
            this.add_link(notebook_id, nbname, item);
            if (!IPython.read_only){
                // hide delete buttons when readonly
                if(kernel == null){
                    this.add_delete_button(item);
                } else {
                    this.add_shutdown_button(item,kernel);
                }
            }
        };
    };

    NotebookList.prototype.list_loaded = function (data, status, xhr) {
        var base_project = $('body').data('project');
        new_data = this.split_data(data);
        for (proj in new_data){
            this.project_notebook_list_load(proj, new_data[proj]);
        }
        $('div.project_name').addClass('list_header ui-widget ui-widget-header');
    }

    NotebookList.prototype.split_data = function (data) {
        new_data = {}
        var base_project = $('body').data('project');
        new_data[base_project] = [];

        for(var i=0; i < data.length;i++) {
            var nb = data[i];
            var proj = null
            if (nb.name.indexOf('/') == -1){
                proj = base_project;
            } else {
                bits = nb.name.split('/');
                name = bits.pop();
                proj = bits.join('/');
            }
            if(new_data[proj] == undefined){
                new_data[proj] = [];
            }
            new_data[proj].push(nb);
        }
        return new_data;
    }

    NotebookList.prototype.new_project_div = function (project) {
        var item = $('<div/>');
        item.addClass('project-notebook-list');
        item.attr('project', project);
        var item_name = $('<div/>').addClass('project_name');
        var h2 = $('<h2/>');
        h2.html(project);
        item_name.append(h2);
        item.append(item_name);

        var project_list = this.element     
        project_list.append(item);
        return item;
    };

    NotebookList.prototype.new_notebook_item = function (index, pdiv) {
        if(!pdiv){
            pdiv = this.element;
        }
        var item = $('<div/>');
        item.addClass('list_item ui-widget ui-widget-content ui-helper-clearfix');
        item.css('border-top-style','none');
        var item_name = $('<span/>').addClass('item_name');

        item.append(item_name);
        if (index === -1) {
            pdiv.append(item);
        } else {
            pdiv.children().eq(index).after(item);
        }
        return item;
    };


    NotebookList.prototype.add_link = function (notebook_id, nbname, item) {
        item.data('nbname', nbname);
        item.data('notebook_id', notebook_id);
        var new_item_name = $('<span/>').addClass('item_name');
        var href = $('body').data('baseProjectUrl')+notebook_id;
        if (nbname.indexOf('/') != -1){
          href = '/n/'+nbname;
        }
        new_item_name.append(
            $('<a/>').
            attr('href', href).
            attr('target','_blank').
            text(nbname.split('/').pop())
        );
        var e = item.find('.item_name');
        if (e.length === 0) {
            item.append(new_item_name);
        } else {
            e.replaceWith(new_item_name);
        };
    };


    NotebookList.prototype.add_name_input = function (nbname, item) {
        item.data('nbname', nbname);
        var new_item_name = $('<span/>').addClass('item_name');
        new_item_name.append(
            $('<input/>').addClass('ui-widget ui-widget-content').
            attr('value', nbname).
            attr('size', '30').
            attr('type', 'text')
        );
        var e = item.find('.item_name');
        if (e.length === 0) {
            item.append(new_item_name);
        } else {
            e.replaceWith(new_item_name);
        };
    };


    NotebookList.prototype.add_notebook_data = function (data, item) {
        item.data('nbdata',data);
    };


    NotebookList.prototype.add_shutdown_button = function (item,kernel) {
        var new_buttons = $('<span/>').addClass('item_buttons');
        var that = this;
        var shutdown_button = $('<button>Shutdown</button>').button().
            click(function (e) {
                var settings = {
                    processData : false,
                    cache : false,
                    type : "DELETE",
                    dataType : "json",
                    success : function (data, status, xhr) {
                        that.load_list();
                    }
                };
                var url = $('body').data('baseProjectUrl') + 'kernels/'+kernel;
                $.ajax(url, settings);
            });
        new_buttons.append(shutdown_button);
        var e = item.find('.item_buttons');
        if (e.length === 0) {
            item.append(new_buttons);
        } else {
            e.replaceWith(new_buttons);
        };
    };

    NotebookList.prototype.add_delete_button = function (item) {
        var new_buttons = $('<span/>').addClass('item_buttons');
        var delete_button = $('<button>Delete</button>').button().
            click(function (e) {
                // $(this) is the button that was clicked.
                var that = $(this);
                // We use the nbname and notebook_id from the parent notebook_item element's
                // data because the outer scopes values change as we iterate through the loop.
                var parent_item = that.parents('div.list_item');
                var nbname = parent_item.data('nbname');
                var notebook_id = parent_item.data('notebook_id');
                var dialog = $('<div/>');
                dialog.html('Are you sure you want to permanently delete the notebook: ' + nbname + '?');
                parent_item.append(dialog);
                dialog.dialog({
                    resizable: false,
                    modal: true,
                    title: "Delete notebook",
                    buttons : {
                        "Delete": function () {
                            var settings = {
                                processData : false,
                                cache : false,
                                type : "DELETE",
                                dataType : "json",
                                success : function (data, status, xhr) {
                                    parent_item.remove();
                                }
                            };
                            var url = $('body').data('baseProjectUrl') + 'notebooks/' + notebook_id;
                            $.ajax(url, settings);
                            $(this).dialog('close');
                        },
                        "Cancel": function () {
                            $(this).dialog('close');
                        }
                    }
                });
            });
        new_buttons.append(delete_button);
        var e = item.find('.item_buttons');
        if (e.length === 0) {
            item.append(new_buttons);
        } else {
            e.replaceWith(new_buttons);
        };
    };


    NotebookList.prototype.add_upload_button = function (item) {
        var that = this;
        var new_buttons = $('<span/>').addClass('item_buttons');
        var upload_button = $('<button>Upload</button>').button().
            addClass('upload-button').
            click(function (e) {
                var nbname = item.find('.item_name > input').attr('value');
                var nbformat = item.data('nbformat');
                var nbdata = item.data('nbdata');
                var content_type = 'text/plain';
                if (nbformat === 'json') {
                    content_type = 'application/json';
                } else if (nbformat === 'py') {
                    content_type = 'application/x-python';
                };
                var settings = {
                    processData : false,
                    cache : false,
                    type : 'POST',
                    dataType : 'json',
                    data : nbdata,
                    headers : {'Content-Type': content_type},
                    success : function (data, status, xhr) {
                        that.add_link(data, nbname, item);
                        that.add_delete_button(item);
                    }
                };

                var qs = $.param({name:nbname, format:nbformat});
                var url = $('body').data('baseProjectUrl') + 'notebooks?' + qs;
                $.ajax(url, settings);
            });
        var cancel_button = $('<button>Cancel</button>').button().
            click(function (e) {
                item.remove();
            });
        upload_button.addClass('upload_button');
        new_buttons.append(upload_button).append(cancel_button);
        var e = item.find('.item_buttons');
        if (e.length === 0) {
            item.append(new_buttons);
        } else {
            e.replaceWith(new_buttons);
        };
    };


    IPython.NotebookList = NotebookList;

    return IPython;

}(IPython));


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

    var NotebookList = function (selector, type, key) {
        this.selector = selector;
        this.type = type
        this.key = key;
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
        this.element.find('#refresh_notebook_list').click(function () {
            that.load_list();
        });
        this.element.bind('dragover', function () {
            return false;
        });
        this.element.bind('drop', function(event){
            that.handelFilesUpload(event,'drop');
            return false;
        });
        console.log(this.element)
        this.element.parent().data('nblist', that)
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
        if (this.type == 'tag') {
          url = $('body').data('baseProjectUrl') + 'tag/' + this.key;
          if (this.key == 'showall') {
            // meh
            url = $('body').data('baseProjectUrl') + 'all_notebooks';
          }
        }
        if (this.type == 'dir') {
          url = $('body').data('baseProjectUrl') + 'dir_notebooks/' + this.key;
        }
        $.ajax(url, settings);
    };


    NotebookList.prototype.project_notebook_list_load = function (project) {
        pdiv = this.element.find('.project-notebook-list[project="'+project['path']+'"]')[0];
        if(!pdiv){
            pdiv = this.new_project_div(project);
        }
        data = project['files'];
        if (!data) {
          return;
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
        projects = this.split_data(data);
        for (i in projects){
            this.project_notebook_list_load(projects[i]);
        }
        $('div.project_name').addClass('list_header ui-widget ui-widget-header');
    }

    NotebookList.prototype.split_data = function (data) {
        new_data = {}
        var base_project = $('body').data('project');
        new_data[base_project] = [];

        projects = data['projects'];
        files = data['files'];
        for(var i=0; i < files.length;i++) {
            var nb = files[i];
            var proj = null;
            if (nb.project_path) {
                proj = nb.project_path;
                name = nb.name;
            } else {
                bits = nb.path.split('/');
                name = bits.pop();
                proj = bits.join('/');
            }
            if(new_data[proj] == undefined){
                new_data[proj] = [];
            }
            new_data[proj].push(nb);
        }

        for (project_path in new_data) {
          var project = null;
          for (p in projects) {
            if (projects[p].path == project_path) {
              project = projects[p];
            }
          }
          if (project) {
              project['files'] = new_data[project_path];
          }
        }
        return projects;
    }

    NotebookList.prototype.new_project_div = function (project) {
        var item = $('<div/>');
        item.addClass('project-notebook-list');
        item.attr('project', project['path']);
        var item_name = $('<div/>').addClass('project_name');
        var h2 = $('<h2/>');
        var display_name = project['name']
        var bits = display_name.split('/')
        if (bits.length > 3) {
          display_name = bits.slice(-2).join('/')
        }
        var href = '/ndir/'+project['path']
          var link = $('<a/>').
          attr('href', href).
          attr('target','_blank').
          text(display_name)
        h2.append(link);
        item_name.append(h2);

        var new_but = $('<button>New Notebook</button>').addClass('new-notebook');
        new_but.button().click(function (e) {
                content_type = 'application/json';

                console.log($(this));
                var par = $(this).parent().parent();
                project_path = $(par).attr('project');
                data = {'project_path':project_path};
                var settings = {
                    cache : false,
                    type : "POST",
                    data : data,
                };

                var w = window.open('');
                settings['success'] = function (data, status, xhr) {
                    data = eval('['+data+']');
                    data = data[0]
                    notebook_id = data['notebook_id'];
                    var  loc = window.location
                    var url = loc.protocol + '//' + loc.hostname + ':' + loc.port + '/' + notebook_id;
                    w.location = url;
                };

                var url = $('body').data('baseProjectUrl') +'new';
                $.ajax(url, settings);
            });
        new_but.button()

        var new_pub_but = $('<button>New Public Notebook</button>').addClass('new-pub-notebook');
        new_pub_but.button().click(function (e) {
                content_type = 'application/json';

                console.log($(this));
                var par = $(this).parent().parent();
                project_path = $(par).attr('project');
                data = {'project_path':project_path};
                // meh only difference
                data['public'] = true
                var settings = {
                    cache : false,
                    type : "POST",
                    data : data,
                };

                var w = window.open('');
                settings['success'] = function (data, status, xhr) {
                    data = eval('['+data+']');
                    data = data[0]
                    notebook_id = data['notebook_id'];
                    var href = window.location.href.split('#')[0]
                    var url = href + notebook_id;
                    w.location = url;
                };

                var url = $('body').data('baseProjectUrl') +'new';
                $.ajax(url, settings);
            });
        new_pub_but.button()
        item_name.append(new_but);
        item_name.append(new_pub_but);
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
        new_item_name.append(
            $('<a/>').
            attr('href', href).
            attr('target','_blank').
            text(nbname)
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


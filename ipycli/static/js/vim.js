// Override CodeCell codemirror
old_handle_keyevent = IPython.CodeCell.prototype._handle_codemirror_keyevent ;
IPython.CodeCell.prototype._base_handle_codemirror_keyevent = old_handle_keyevent;

IPython.CodeCell.prototype.handle_codemirror_keyevent = function (editor, event) {
  var ret =  this._base_handle_codemirror_keyevent(editor, event);
  if(ret != null) {
    return ret;
  }

  if( event.type == 'keydown' && this.notebook.keyMap == 'vim') {
    ret = IPython.VIM.keyDown(this.notebook, event);
    return ret;
  }
  return false;
}

// Override TextCell keydown
// Really just here to handle the render/editing of text cells
// Might need to consider also using codemirror keyevent
old_handle_keydown = IPython.TextCell.prototype.handle_keydown ;
IPython.TextCell.prototype._base_handle_keydown = old_handle_keydown;

IPython.TextCell.prototype.handle_keydown = function (event) {
  var ret =  this._base_handle_keydown(event);
  if(ret != null) {
    return ret;
  }

  if( event.type == 'keydown' && this.notebook.keyMap == 'vim') {
    ret = IPython.VIM.keyDown(this.notebook, event);
    return ret;
  }
  return false;
}

IPython.Notebook.prototype.setVIMode = function (mode) {
  var cell = this.get_selected_cell();
  cm = cell.code_mirror;
  if(cm) {
    if(mode == 'INSERT') {
      CodeMirror.keyMap.vim.I(cm);
    }
  }
}

var IPython = (function (IPython) {

  var NormalMode = {};
  var InsertMode = {};

  var VIM = function() {;};
    
  VIM.prototype.keyDown = function(that, event) {
    var cell = that.get_selected_cell();
    var vim_mode = cell.code_mirror.getOption('keyMap');

    ret = false;

    if(vim_mode == 'vim') {
      ret = NormalMode.keyDown(that, event);
    }

    if(vim_mode == 'vim-insert') {
      ret = InsertMode.keyDown(that, event);
    }

    if(ret) {
      event.preventDefault();
      return true;
    }
  };

  NormalMode.keyDown = function(that, event) {
    var cell = that.get_selected_cell();
    var cell_type = cell.cell_type;
    var textcell = cell instanceof IPython.TextCell;


    // ` : enable console
    if (event.which === 192) {
      $(IPython.console_book.element).toggle();
      IPython.console_book.focus_selected();
      return true;
    }

    // K: up cell
    if (event.which === 75 && event.shiftKey) 
    {
        that.select_prev();
        return true;
    } 
      if (event.which === 75 && (event.metaKey)) {
          that.select_prev();
          return true;
      }
    // k: up
    if (event.which === 75 && !event.shiftKey) 
    {
        if (cell.at_top()) {
          that.select_prev();
          return true;
        };
    } 
    // J: down cell
    if (event.which === 74 && event.shiftKey) {
        that.select_next();
        return true;
    }
      if (event.which === 74 && (event.metaKey)) {
          that.select_next();
          return true;
      }
    // j: down
    if (event.which === 74 && !event.shiftKey) {
          if (cell.at_bottom()) {
            that.select_next();
            return true;
          };
    }
    // Y: copy cell
    if (event.which === 89 && event.shiftKey) {
        that.copy_cell();
        return true;
    }
    // D: delete cell / cut
    if (event.which === 68 && event.shiftKey) {
        that.cut_cell();
        return true;
    }
    // P: paste cell
    if (event.which === 80 && event.shiftKey) {
        that.paste_cell();
        return true;
    }
    // B: open new cell below
    if (event.which === 66 && event.shiftKey) {
        that.insert_cell_below('code');
        that.setVIMode('INSERT');
        return true;
    }
    // shift+O or apple + O: open new cell below
    // I know this is wrong but i hate hitting A
    if (event.which === 79 && (event.metaKey || event.shiftKey)) {
        that.insert_cell_below('code');
        that.setVIMode('INSERT');
        return true;
    }
    // A: open new cell above
    if (event.which === 65 && event.shiftKey) {
      that.insert_cell_above('code');
      that.setVIMode('INSERT');
      return true;
    }
    // control/apple E: execute (apple - E is easier than shift E)
    if ((event.ctrlKey || event.metaKey) && event.keyCode==69) { 
      that.execute_selected_cell({addnew:false, select_next:false});
      return true;
    }
    // E:  execute
    if (event.which === 69 && event.shiftKey) {
      that.execute_selected_cell({addnew:false, select_next:false});
      return true;
    }
    // F: toggle output
    if (event.which === 70 && event.shiftKey) {
      that.toggle_output();
      return true;
    }
    // M: markdown
    if (event.which === 77 && event.shiftKey) {
      that.to_markdown();
      return true;
    }
    // C: codecell
    if (event.which === 77 && event.shiftKey) {
      that.to_code();
      return true;
    }
    // i: insert. only relevant on textcell
    var rendered = cell.rendered;
    if (textcell && rendered && event.which === 73 && !event.shiftKey) {
      cell.edit();
      return false;
    }

    // esc: get out of insert and render textcell
    if (textcell && !rendered && event.which === 27 && !event.shiftKey) {
        cell.render();
        return false;
    } 
  };

  InsertMode.keyDown = function(that, event) {
    var cell = that.get_selected_cell();
    var cell_type = cell.cell_type;
    var textcell = cell instanceof IPython.TextCell;

    // control/apple E: execute (apple - E is easier than shift E)
    if ((event.ctrlKey || event.metaKey) && event.keyCode==69) { 
      that.execute_selected_cell({addnew:false, select_next:false});
      return true;
    }
    if (event.which === 74 && (event.metaKey)) {
        that.select_next();
        return true;
    }
      if (event.which === 75 && (event.metaKey)) {
          that.select_prev();
          return true;
      }
  };

  IPython.VIM = new VIM();
  return IPython;

}(IPython));


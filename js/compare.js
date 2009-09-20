var users_to_compare = new Array();

function checkboxClicked(event) {
  if ($F(this) == null) { // unselected
    users_to_compare = users_to_compare.without(this.id.substr(4));
    $(this).up().previous().removeClassName('selected');
    if (users_to_compare.length == 0) {
      $('compare_btn').hide();
    }
  } else { // selected
    users_to_compare.push(this.id.substr(4));
    $(this).up().previous().addClassName('selected');
    if (users_to_compare.length == 2) {
      $('compare_btn').show();
    }
  }
}

$$('.rank_chkbox input').each(function(obj){
  obj.observe('click', checkboxClicked);
  if ($F(obj) != null) {
    $(obj).up().previous().addClassName('selected');
  }
});

Event.observe('compare_btn', 'click', function(event) {
  window.location.href = '/users/compare?users=' + users_to_compare.join('-');
});

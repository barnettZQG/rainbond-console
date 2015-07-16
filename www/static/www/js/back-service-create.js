//服务创建
function service_create(tenantName, service_key) {
	window.location.href = "/apps/" + tenantName
			+ "/service-deploy/?service_key=" + service_key
}
//创建应用
$(function(){
    $('#create_service_name').blur(function(){
        var appName = $(this).val(),
            checkReg = /^[a-zA-Z][a-zA-Z0-9_-]*$/,
            result = true;
            
        if(!checkReg.test(appName)){
            $('#create_service_notice').slideDown();
            return;
        }else{
            $('#create_service_notice').slideUp();
        }
    });
    //第一步
    $('#back_service_finished').click(function(){
        var appName = $('#create_service_name').val(),
            checkReg = /^[a-zA-Z][a-zA-Z0-9_-]*$/,
            result = true;
            
        if(!checkReg.test(appName)){
            $('#create_service_notice').slideDown();
            return;
        }else{
            $('#create_service_notice').slideUp();
        }    
        
        var service_dependecy = $("#service_dependecy").val()
        var serviceKey="";
		var serviceId="";
		var _selectValue = $('input[type="radio"][name="delineCheckbox1"]:checked').val()
		var str = _selectValue.split("_");
		if(str[0] == service_dependecy){
			$("#createService").val(str[0])
			$("#hasService").val("")
		}else{
			$("#hasService").val(str[0])
			$("#createService").val("")
		}
		var createService = $("#createService").val()
		var hasService = $('#hasService').val()
		
		if(service_dependecy !=""){			
			if(createService=="" && hasService==""){
				$('#create_dependency_service_notice').slideDown();
				return;
			}
		}
		var tenantName = $("#tenantName").val()
		$("#back_service_finished").attr('disabled', "true")
		var _data = $("form").serialize();
    	$.ajax({
    		type : "post",
    		url : "/apps/" + tenantName + "/service-deploy/",
    		data : _data,
    		cache : false,
    		beforeSend : function(xhr, settings) {
    			var csrftoken = $.cookie('csrftoken');
    			xhr.setRequestHeader("X-CSRFToken", csrftoken);
    		},
    		success : function(msg) {
    			var dataObj = msg;
    			if (dataObj["status"] == "notexist"){
    				swal("所选的服务类型不存在");
    				$("#back_service_finished").removeAttr('disabled')
    			} else if (dataObj["status"] == "exist") {
    				swal("服务名已存在");
    				$("#back_service_finished").removeAttr('disabled')
    			} else if (dataObj["status"] == "overtop") {
    				swal("免费资源已达上限，不能创建");
    				$("#back_service_finished").removeAttr('disabled')
    			} else if (dataObj["status"] == "empty") {
    				swal("服务名称不能为空");
    				$("#back_service_finished").removeAttr('disabled')
    			}else if (dataObj["status"] == "success") {
    				service_alias = dataObj["service_alias"]
    				window.location.href = "/apps/" + tenantName + "/" + service_alias + "/detail/";
    			} else {
    				swal("创建失败");
    				$("#back_service_finished").removeAttr('disabled')
                }
    		},
    		error : function() {
    			swal("系统异常,请重试");
    			$("#back_service_finished").removeAttr('disabled')
    		}
    	})
    });
});
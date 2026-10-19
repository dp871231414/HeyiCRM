package com.heyi.publics.entity.form;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class UserSaveForm {

    @NotBlank(message = "姓名不能为空")
    private String name;

    @NotBlank(message = "账号不能为空")
    private String account;

    private String password;
    private Long deptId;
    private Long roleId;
    private String scope;
    private String status;
}

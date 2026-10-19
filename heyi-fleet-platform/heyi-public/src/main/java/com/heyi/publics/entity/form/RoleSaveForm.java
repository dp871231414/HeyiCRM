package com.heyi.publics.entity.form;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.util.List;

@Data
public class RoleSaveForm {

    @NotBlank(message = "角色名称不能为空")
    private String name;
    private String description;
    private String scope;
    private List<String> permissions;
}

package com.heyi.publics.entity.form;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class OrganizationSaveForm {

    @NotBlank(message = "部门名称不能为空")
    private String name;
    private String type;
    private Long parentId;
    private String head;
    private Integer sortOrder;
}

package com.heyi.publics.entity.form;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.util.List;

@Data
public class SysDictSaveForm {

    @NotBlank(message = "字典名称不能为空")
    private String name;

    private String code;
    /** 枚举值整份替换 */
    private List<String> values;
}

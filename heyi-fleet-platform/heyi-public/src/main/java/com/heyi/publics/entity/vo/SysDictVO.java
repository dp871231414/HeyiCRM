package com.heyi.publics.entity.vo;

import lombok.Data;

import java.util.List;

@Data
public class SysDictVO {

    private Long id;
    private String code;
    private String name;
    private List<String> values;
}

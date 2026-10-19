package com.heyi.modules.system.service.impl;

import com.heyi.modules.system.mapper.SysDictMapper;
import com.heyi.modules.system.service.SysDictService;
import com.heyi.publics.common.base.SuperServiceImpl;
import com.heyi.publics.entity.SysDict;
import org.springframework.stereotype.Service;

@Service
public class SysDictServiceImpl extends SuperServiceImpl<SysDictMapper, SysDict> implements SysDictService {
}

package com.heyi.server;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

/**
 * 启动类。组件扫描覆盖 com.heyi 全系包（含 publics / modules）；
 * Mapper 接口需单独声明扫描路径，否则不会被注册为 Bean。
 */
@SpringBootApplication(scanBasePackages = "com.heyi")
@ConfigurationPropertiesScan
@MapperScan("com.heyi.modules.**.mapper")
public class HeYiFleetApplication {

    public static void main(String[] args) {
        SpringApplication.run(HeYiFleetApplication.class, args);
    }
}
